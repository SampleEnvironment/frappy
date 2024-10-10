
from frappy.gui.cfg_editor.utils import get_modules, get_module_class_from_name

def test_module_imports():
    def all_classes(tree):
        for k, v in tree.items():
            for d, l in v.items():
                for m in l:
                    yield f'{k}.{d}.{m}'

    module_tree = get_modules()
    for clsname in all_classes(module_tree):
        get_module_class_from_name(clsname)
