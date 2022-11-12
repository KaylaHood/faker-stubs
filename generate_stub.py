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


def get_members(cls: object) -> List[Tuple[str, Tuple[type, Any]]]:
    members = [(name, (cls, value)) for (name, value) in inspect.getmembers(cls) 
               if not name.startswith("_")]
    return members

classes_and_locales_to_use_for_stub: List[Tuple[object, str]] = [(faker.Faker, None)]
for locale in AVAILABLE_LOCALES:
    for provider in PROVIDERS:
        if provider == "faker.providers":
            continue
        prov_cls, _, _ = Factory._find_provider_class(provider, locale)
        classes_and_locales_to_use_for_stub.append((prov_cls, locale))

unique_members = {mbr[0]: (*mbr[1], locale) 
                  for cls, locale in classes_and_locales_to_use_for_stub 
                  for mbr in get_members(cls)}

imports = defaultdict(set)
imports["typing"] = {"TypeVar"}
imports["enum"] = {"Enum"}
# list of tuples. First elem of tuple is the signature string,
#  second is the comment string,
#  third is a boolean which is True if the comment precedes the signature
signatures_with_comments: List[Tuple[str, str, bool]] = []
for name, (prov_cls, value, locale) in unique_members.items():
    attr = getattr(prov_cls, name, None)
    if attr is not None and (inspect.isfunction(attr) or inspect.ismethod(attr)):
        sig = inspect.signature(value)
        comment = inspect.getdoc(value)
        if (sig.return_annotation is not None 
            and sig.return_annotation is not inspect.Signature.empty 
            and sig.return_annotation.__module__ != "builtins"):
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
        signatures_with_comments.append((f"def {name}{sig_str}: ...", None if comment == "" else comment, False))
    else:
        new_modules = []
        type_module = getattr(type(value), "__module__", None)
        comment = inspect.getcomments(value)
        if type_module is not None and type_module != "builtins":
            module, member = get_module_and_member(type(value), locale)
            if module is not None and member is not None:
                imports[module].add(member)
                new_modules.append(module)
        type_str = type(value).__name__.replace("Ellipsis", "...").replace("NoneType", "None").replace("~", "")
        for module in new_modules:
            type_str = type_str.replace(f"{module}.", "")
        signatures_with_comments.append((f"{name}: {type_str}", comment, True))

signatures_with_comments_as_str = []
for sig, comment, is_preceding_comment in signatures_with_comments:
    if comment is not None and is_preceding_comment:
        signatures_with_comments_as_str.append(f"# {comment}\n    {sig}")
    elif comment is not None:
        signatures_with_comments_as_str.append(sig + "\n    \"\"\"" + comment.replace("\n", "\n    ") + "\n    \"\"\"")
    else:
        signatures_with_comments_as_str.append(sig)

imports_block = "\n".join([f"from {module} import {', '.join(names)}" for module, names in imports.items()])
member_signatures_block = "    " + "\n    ".join(signatures_with_comments_as_str)

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