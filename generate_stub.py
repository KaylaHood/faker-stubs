from collections import defaultdict
import inspect
import pathlib
import re
from typing import Any, Dict, List, Tuple
from faker.config import AVAILABLE_LOCALES, PROVIDERS
from faker import Factory

import faker.proxy


def get_module_and_member(cls, locale = None) -> Tuple[str, str]:
    cls_name = getattr(cls, '__name__', getattr(cls, '_name', str(cls)))
    module, member = cls.__module__, cls_name
    if cls_name is None:
        qualified_type = re.findall(r'([a-zA-Z_0-9]+)\.([a-zA-Z_0-9]+)', str(cls))
        if len(qualified_type) > 0:
            if qualified_type[0][1] not in imports[qualified_type[0][0]]:
                module, member = qualified_type[0]
        else:
            unqualified_type = re.findall(r'[^\.a-zA-Z0-9_]([A-Z][a-zA-Z0-9_]+)[^\.a-zA-Z0-9_]', ' ' + str(cls) + ' ')
            if len(unqualified_type) > 0 and unqualified_type[0] != "NoneType":
                cls_str = str(cls).replace('.en_US', '').replace("faker.", ".")
                if "<class '" in cls_str:
                    cls_str = cls_str.split("'")[1]
                if locale is not None:
                    cls_str = cls_str.replace('.'+locale, '')
                if unqualified_type[0] not in imports[cls_str]:
                    module, member = cls_str, unqualified_type[0]
    return module, member


seen_funcs = set()
seen_vars = set()


class UniqueMemberFunctionsAndVariables:
    def __init__(self, cls: type, funcs: Dict[str, Any], vars: Dict[str, Any]):
        global seen_funcs, seen_vars
        self.cls = cls
        self.funcs = funcs
        for func_name in seen_funcs:
            self.funcs.pop(func_name, None)
        seen_funcs = seen_funcs.union(self.funcs.keys())

        self.vars = vars
        for var_name in seen_vars:
            self.vars.pop(var_name, None)
        seen_vars = seen_vars.union(self.vars.keys())
        

def get_member_functions_and_variables(cls: object, include_mangled: bool = False) \
                                       -> UniqueMemberFunctionsAndVariables:
    members = [(name, value) for (name, value) in inspect.getmembers(cls) 
               if ((include_mangled and name.startswith("__")) or not name.startswith("_"))]
    funcs: Dict[str, Any] = {}
    vars: Dict[str, Any] = {}
    for (name, value) in members:
        attr = getattr(cls, name, None)
        if attr is not None and (inspect.isfunction(attr) or inspect.ismethod(attr)):
            funcs[name] = value
        else:
            vars[name] = value

    return UniqueMemberFunctionsAndVariables(cls, funcs, vars)


classes_and_locales_to_use_for_stub: List[Tuple[object, str]] = []
for locale in AVAILABLE_LOCALES:
    for provider in PROVIDERS:
        if provider == "faker.providers":
            continue
        prov_cls, _, _ = Factory._find_provider_class(provider, locale)
        classes_and_locales_to_use_for_stub.append((prov_cls, locale))

all_members: List[Tuple[UniqueMemberFunctionsAndVariables, str]] = \
    [(get_member_functions_and_variables(cls), locale) for cls, locale in classes_and_locales_to_use_for_stub] \
    + [(get_member_functions_and_variables(faker.Faker, include_mangled=True), None)]

# Use the accumulated seen_funcs and seen_vars to remove all variables that have the same name as a function somewhere
overlapping_var_names = seen_vars.intersection(seen_funcs)
for mbr_funcs_and_vars, _ in all_members:
    for var_name_to_remove in overlapping_var_names:
        mbr_funcs_and_vars.vars.pop(var_name_to_remove, None)

imports = defaultdict(set)
imports["typing"] = {"TypeVar"}
imports["enum"] = {"Enum"}

# list of tuples. First elem of tuple is the signature string,
#  second is the comment string,
#  third is a boolean which is True if the comment precedes the signature
signatures_with_comments: List[Tuple[str, str, bool]] = []

for mbr_funcs_and_vars, locale in all_members:
    for func_name, func_value in mbr_funcs_and_vars.funcs.items():
        sig = inspect.signature(func_value)
        ret_annot_module = getattr(sig.return_annotation, "__module__", None)
        if (not sig.return_annotation in [None, inspect.Signature.empty, prov_cls.__name__]
            and not ret_annot_module in [None, "builtins"]):
            module, member = get_module_and_member(sig.return_annotation, locale)
            if module is not None and member is not None:
                imports[module].add(member)
        
        new_parms = []
        for key, parm_val in sig.parameters.items():
            new_parm = parm_val
            if parm_val.default is not inspect.Parameter.empty:
                new_parm = parm_val.replace(default=...)
            if (new_parm.annotation is not inspect.Parameter.empty 
                and new_parm.annotation.__module__ != "builtins"):
                module, member = get_module_and_member(new_parm.annotation, locale)
                if module is not None and member is not None:
                    imports[module].add(member)
            new_parms.append(new_parm)
        
        sig = sig.replace(parameters=new_parms)
        sig_str = str(sig).replace("Ellipsis", "...").replace("NoneType", "None").replace("~", "")
        for module in imports.keys():
            sig_str = sig_str.replace(f"{module}.", "")

        comment = inspect.getdoc(func_value)
        signatures_with_comments.append((f"def {func_name}{sig_str}: ...", None if comment == "" else comment, False))
    for var_name, var_value in mbr_funcs_and_vars.vars.items():
        new_modules = []
        type_module = getattr(type(var_value), "__module__", None)
        if type_module is not None and type_module != "builtins":
            module, member = get_module_and_member(type(var_value), locale)
            if module is not None and member is not None:
                imports[module].add(member)
                new_modules.append(module)
        
        type_str = type(var_value).__name__.replace("Ellipsis", "...").replace("NoneType", "None").replace("~", "")
        for module in new_modules:
            type_str = type_str.replace(f"{module}.", "")
        
        comment = inspect.getcomments(var_value)
        signatures_with_comments.append((f"{var_name}: {type_str}", comment, True))

signatures_with_comments_as_str = []
for sig, comment, is_preceding_comment in signatures_with_comments:
    if comment is not None and is_preceding_comment:
        signatures_with_comments_as_str.append(f"# {comment}\n    {sig}")
    elif comment is not None:
        sig_without_final_ellipsis = sig.strip(" .")
        signatures_with_comments_as_str.append(sig_without_final_ellipsis + "\n    \"\"\"\n    " 
                                               + comment.replace("\n", "\n    ") + "\n    \"\"\"\n    ...")
    else:
        signatures_with_comments_as_str.append(sig)

imports_block = "\n".join([f"from {module} import {', '.join(names)}" for module, names in imports.items()])
member_signatures_block = "    " + "\n    ".join([sig.replace("\n", "\n    ") for sig in signatures_with_comments_as_str])

body = \
f"""
{imports_block}

T = TypeVar(\"T\")
TEnum = TypeVar("TEnum", bound=Enum)

class Faker:
{member_signatures_block}
"""

faker_proxy_path = pathlib.Path(inspect.getfile(faker.proxy))
stub_file_path = faker_proxy_path.with_name("proxy.pyi").resolve()
with open(stub_file_path, "w", encoding="utf-8") as fh:
    fh.write(body)