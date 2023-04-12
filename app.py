import ast
import astor
from io import StringIO
from collections import defaultdict
import re
from nbconvert import PythonExporter
import tempfile
import subprocess
from pathlib import Path

import streamlit as st
from tree_transformers import IpywidgetsToStreamlitTransformer


def remove_unused_imports(code_string):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / "temp.py"
        with open(temp_file, 'w') as f:
            f.write(code_string)

        # Run autoflake to remove unused imports
        autoflake_command = f"autoflake --remove-all-unused-imports --remove-duplicate-keys --in-place {temp_file}"
        subprocess.run(autoflake_command.split())

        # Read the cleaned code
        with open(temp_file, 'r') as f:
            cleaned_code = f.read()

    return cleaned_code


def remove_duplicate_imports(tree):
    imports = defaultdict(set)

    # Collect all unique imports
    new_body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            for name in node.names:
                alias = (module, name.name, name.asname)
                if alias not in imports[module]:
                    imports[module].add(alias)
                    new_body.append(node)
        else:
            new_body.append(node)

    # Update the tree with the new body and unparse it
    tree.body = new_body

    return tree


def convert(input_code: str) -> str:
    python_exporter = PythonExporter()
    exported_code, _ = python_exporter.from_file(StringIO(input_code))
    exported_code = re.sub(r"[#%].*", "", exported_code)
    tree = ast.parse(exported_code, "", "exec")
    transformer = IpywidgetsToStreamlitTransformer()
    output_ast = transformer.visit(tree)
    output_code = astor.to_source(remove_duplicate_imports(output_ast))
    clean_code = remove_unused_imports(output_code)
    return clean_code


st.title("Ipython -> Streamlit converter")

uploader = st.file_uploader("Upload *.ipynb file", type="ipynb")

if uploader:
    input_code = uploader.getvalue().decode("utf-8")
    with st.expander("Input code"):
        st.code(input_code, language="python", line_numbers=True)
    output_code = convert(input_code)
    with st.expander("Output code"):
        st.code(output_code, language="python", line_numbers=True)
    with open("pages/output.py", "w") as f:
        f.write(output_code)



