from collections import defaultdict
import inspect
import pathlib
import re
from typing import Tuple
from faker.config import AVAILABLE_LOCALES, PROVIDERS
from faker import Factory

import faker.proxy


def get_module_and_member(cls) -> Tuple[str, str]:
    cls_name = getattr(cls, '__name__', getattr(cls, '_name', str(cls)))
    module, member = cls.__module__, cls_name
    if cls_name is None:
        qualified_types = re.findall(r'([a-zA-Z_0-9]+)\.([a-zA-Z_0-9]+)', str(cls))
        for module, member_name in qualified_types:
            if member_name not in imports[module]:
                module, member = module, member_name
        unqualified_types = re.findall(r'[^\.a-zA-Z0-9_]([A-Z][a-zA-Z0-9_]+)[^\.a-zA-Z0-9_]', ' ' + str(cls) + ' ')
        for type_name in unqualified_types:
            if type_name == "NoneType":
                continue
            cls_str = str(prov_cls).replace('.en_US', '').replace('.'+locale, '').split("'")[1].replace("faker.", ".")
            if type_name not in imports[cls_str]:
                module, member = cls_str, type_name
    return module, member
    

unique_members = {}
for locale in AVAILABLE_LOCALES:
    for provider in PROVIDERS:
        if provider == "faker.providers":
            continue
        prov_cls, _, _ = Factory._find_provider_class(provider, locale)
        members = {name: (prov_cls, locale, value) for (name, value) in inspect.getmembers(prov_cls) 
                   if not name.startswith("_")}
        unique_members.update(members)
faker_members = {name: (faker.Faker, None, value) for (name, value) in inspect.getmembers(faker.Faker) 
                 if not name.startswith("_")}
unique_members.update(faker_members)

imports = defaultdict(set)
imports["typing"] = {"TypeVar"}
imports["enum"] = {"Enum"}
signatures = []
for name, (prov_cls, locale, value) in unique_members.items():
    attr = getattr(prov_cls, name, None)
    if attr is not None and inspect.isfunction(attr) or inspect.ismethod(attr):
        sig = inspect.signature(value)
        if (sig.return_annotation is not None 
            and sig.return_annotation is not inspect.Signature.empty 
            and sig.return_annotation.__module__ != "builtins"):
            module, member = get_module_and_member(sig.return_annotation)
            if module is not None and member is not None:
                imports[module].add(member)
        new_parms = []
        for key, parm_val in sig.parameters.items():
            new_parm = parm_val
            if parm_val.default is not inspect.Parameter.empty:
                new_parm = parm_val.replace(default=...)
            if (new_parm.annotation is not inspect.Parameter.empty 
                and new_parm.annotation.__module__ != "builtins"):
                module, member = get_module_and_member(new_parm.annotation)
                if module is not None and member is not None:
                    imports[module].add(member)
            new_parms.append(new_parm)
        sig = sig.replace(parameters=new_parms)
        sig_str = str(sig).replace("Ellipsis", "...").replace("NoneType", "None").replace("~", "")
        for module in imports.keys():
            sig_str = sig_str.replace(f"{module}.", "")
        signatures.append(f"def {name}{sig_str}: ...")
    else:
        new_modules = []
        type_module = getattr(type(value), "__module__", None)
        if type_module is not None and type_module != "builtins":
            module, member = get_module_and_member(type(value))
            if module is not None and member is not None:
                imports[module].add(member)
                new_modules.append(module)
        type_str = type(value).__name__.replace("Ellipsis", "...").replace("NoneType", "None").replace("~", "")
        for module in new_modules:
            type_str = type_str.replace(f"{module}.", "")
        signatures.append(f"{name}: {type_str}")

imports_block = "\n".join([f"from {module} import {', '.join(names)}" for module, names in imports.items()])
member_signatures_block = "    " + "\n    ".join(signatures)

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
with open(stub_file_path, "w") as fh:
    fh.write(body)