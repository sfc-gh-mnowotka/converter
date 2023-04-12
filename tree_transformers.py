import ast
import matplotlib.colors as mcolors


class IpywidgetsToStreamlitTransformer(ast.NodeTransformer):
    def __init__(self):
        self.ipywidgets_alias = "widgets"
        self.fig_vars = []
        self.module_body = None
        self.converted_functions = {}
        self.file_upload_variables = set()
        self.transformed_variables = set()
        self.args_translation = {
            "description": "label",
            "min": "min_value",
            "max": "max_value",
            "value": "value",
            "step": "step",
            "options": "options",
        }
        self.dropdown_args_translation = {
            "options": "options",
            "value": "index",  # Replace 'value' with 'index'
            "description": "label",
        }
        self.multiselect_args_translation = {
            "description": "label",
            "options": "options",
            "value": "default",
        }
        self.supported_slider_types = [
            "IntSlider",
            "FloatSlider",
            "IntRangeSlider",
            "FloatRangeSlider",
        ]
        self.supported_number_input_types = [
            "BoundedIntText",
            "BoundedFloatText",
            "IntText",
            "FloatText",
        ]
        self.supported_text_types = ["Text", "Password", "Textarea"]
        self.supported_multiselect_types = [
            "SelectMultiple",
            "TagsInput",
        ]
        self.supported_button_types = ["ToggleButton"]

    def visit_Module(self, node):
        self.module_body = node.body
        return self.generic_visit(node)

    def visit_Import(self, node):
        return self._process_import(node)

    def visit_ImportFrom(self, node):
        if node.module == "ipywidgets":
            self.ipywidgets_alias = None
            if not any(alias.name == "streamlit" for alias in node.names):
                # Add a separate import statement for streamlit
                st_import = ast.Import(names=[ast.alias(name="streamlit", asname="st")])
                self.module_body.insert(self.module_body.index(node) + 1, st_import)
        return node

    def visit_Assign(self, node):
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "figure"
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "plt"
        ):
            self.fig_vars.append(node.targets[0].id)

        if isinstance(node.value, ast.Call):
            value = node.value
            func = value.func
            identifier = node.targets[0].id
            if self._is_ipywidgets_button(func):
                node.value = self._process_button_call(node.value)
                return node
            if hasattr(func, "id"):
                if func.id == "interactive":
                    self.transformed_variables.add(identifier)
                    return self._process_interactive(node)
            if hasattr(func, "attr"):
                if func.attr in self.supported_slider_types:
                    self.transformed_variables.add(identifier)
                    return self._process_slider(node)
                if func.attr in self.supported_number_input_types:
                    self.transformed_variables.add(identifier)
                    return self._process_number_input(node)
                if func.attr in self.supported_text_types:
                    self.transformed_variables.add(identifier)
                    text_type = "text_area" if func.attr == "Textarea" else "text_input"
                    return self._process_text_input(node, text_type)
                if func.attr == "Checkbox":
                    self.transformed_variables.add(identifier)
                    return self._process_checkbox(node)
                if func.attr == "Dropdown":
                    self.transformed_variables.add(identifier)
                    return self._process_dropdown(node)
                if func.attr == "RadioButtons":
                    self.transformed_variables.add(identifier)
                    return self._process_radio(node)
                if func.attr == "SelectionSlider":
                    self.transformed_variables.add(identifier)
                    return self._process_selection_slider(node)
                if func.attr in self.supported_multiselect_types:
                    self.transformed_variables.add(identifier)
                    return self._process_multiselect(node)
                if func.attr == "DatePicker":
                    self.transformed_variables.add(identifier)
                    return self._process_datepicker(node)
                if func.attr == "TimePicker":
                    self.transformed_variables.add(identifier)
                    return self._process_time_picker(node)
                if func.attr == "ColorPicker":
                    self.transformed_variables.add(identifier)
                    return self._process_color_picker(node)
                if func.attr == "Image":
                    self.transformed_variables.add(identifier)
                    return self._process_image(node, is_assign=True)
                if func.attr == "FileUpload":
                    return self._process_file_upload(node)
                if func.attr in self.supported_button_types:
                    self.transformed_variables.add(identifier)
                    return self._process_button(node)
        return super().generic_visit(node)

    def visit_Expr(self, node):
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "show"
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "plt"
        ):
            if self.fig_vars:
                fig_var = self.fig_vars.pop(0)
                return ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="st", ctx=ast.Load()),
                            attr="pyplot",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id=fig_var, ctx=ast.Load())],
                        keywords=[],
                    )
                )
            else:
                print("Warning: fig variable not found, please check your code")
                return node

        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "on_click"
        ):
            button_var = node.value.func.value.id
            on_click_callback = node.value.args[0]

            # Find the button assignment statement
            for n in self.module_body:
                if isinstance(n, ast.Assign) and n.targets[0].id == button_var:
                    n.value = self._process_button_call(n.value, on_click_callback)
                    break

            # Remove the on_click Expr node
            return None
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Call)
            and isinstance(node.value.func.value.func, ast.Name)
            and node.value.func.value.func.id == "get_ipython"
        ):
            return None

        if isinstance(node.value, ast.Call):
            if hasattr(node.value.func, "attr") and node.value.func.attr == "display":
                return self._process_display(node)
            if hasattr(node.value.func, "id") and node.value.func.id == "display":
                return self._process_display(node)
            if (
                hasattr(node.value.func, "attr")
                and node.value.func.attr == "Image"
                and node.value.func.value.id == "widgets"
            ):
                return self._process_image(node, is_assign=False)
        return node

    def visit_Attribute(self, node):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in self.transformed_variables
            and node.attr == "value"
        ):
            return node.value

        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "widgets"
            and (
                node.attr in self.supported_slider_types
                or node.attr in self.supported_number_input_types
            )
        ):
            return ast.Name(id="st", ctx=ast.Load())

        return node

    def visit_FunctionDef(self, node):
        self.converted_functions[node.name] = node
        return self.generic_visit(node)

    def visit_Call(self, node):
        # Check if the function being called is the interactive function
        if isinstance(node.func, ast.Name) and node.func.id == "interactive":
            args = [arg for arg in node.args]
            kwargs = {kwarg.arg: kwarg.value for kwarg in node.keywords}

            for arg in args:
                if isinstance(arg, ast.Name) and arg.id in self.converted_functions:
                    function_name = arg.id
                    break
            else:
                return node

            # Find the function definition in the AST
            function_def = None
            for statement in self.module_body:
                if (
                    isinstance(statement, ast.FunctionDef)
                    and statement.name == function_name
                ):
                    function_def = statement
                    break

            if function_def is None:
                return node

            # Extract the parameter names from the function definition
            param_names = [param.arg for param in function_def.args.args]

            # Reorder the keyword arguments according to the function definition
            reordered_kwargs = []
            for param_name in param_names:
                if param_name in kwargs:
                    reordered_kwargs.append(
                        ast.keyword(arg=param_name, value=kwargs[param_name])
                    )

            # Replace the original keyword arguments with the reordered ones
            node.keywords = reordered_kwargs

        return self.generic_visit(node)

    def _is_ipywidgets_button(self, func):
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "Button"
            and isinstance(func.value, ast.Name)
            and func.value.id == self.ipywidgets_alias
        )

    def _process_image(self, node, is_assign):
        st_image = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="image",
            ctx=ast.Load(),
        )

        keywords = []

        for kw in node.value.keywords:
            if kw.arg == "value":
                kw.arg = "image"
            elif kw.arg == "format":
                kw.arg = "output_format"
            elif kw.arg in ["height", "width"]:
                continue  # Skip the 'height' and 'width' keywords
            keywords.append(kw)

        # Add use_column_width argument to use the full column width
        keywords.append(
            ast.keyword(arg="use_column_width", value=ast.NameConstant(value=True))
        )

        st_image_call = ast.Call(func=st_image, args=[], keywords=keywords)
        if is_assign:
            new_assign = ast.Assign(targets=node.targets, value=st_image_call)
            return new_assign
        else:
            return ast.Expr(value=st_image_call)

    def _process_slider(self, node):
        st_slider = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="slider", ctx=ast.Load()
        )

        keywords = []
        description_found = any([kw.arg == "description" for kw in node.value.keywords])

        for kw in node.value.keywords:
            kw.arg = self.args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        if not description_found:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        if any(
            [
                isinstance(kw.value.value, float)
                for kw in keywords
                if isinstance(kw.value, ast.Constant)
            ]
        ):
            for kw in keywords:
                if isinstance(kw.value, ast.Constant) and isinstance(
                    kw.value.value, int
                ):
                    kw.value.value = float(kw.value.value)

        is_range_slider = any(
            [
                isinstance(kw.value, ast.Tuple) or isinstance(kw.value, ast.List)
                for kw in keywords
                if kw.arg == "value"
            ]
        )

        if is_range_slider:
            for kw in keywords:
                if kw.arg == "value":
                    first, second = kw.value.elts
                    if type(first.value) != type(second.value):
                        first.value = float(first.value)
                        second.value = float(second.value)

        st_slider_call = ast.Call(func=st_slider, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_slider_call)
        return new_assign

    def _convert_abbreviation_tuple_to_slider(self, abbreviation, default_value):
        values = [elt.value for elt in abbreviation.elts]

        if len(values) == 2:
            min_value, max_value = values
            step = (
                1 if isinstance(min_value, int) and isinstance(max_value, int) else 0.1
            )
        elif len(values) == 3:
            min_value, max_value, step = values
        else:
            raise ValueError("Invalid abbreviation tuple length")

        slider_type = (
            "IntSlider"
            if isinstance(min_value, int) and isinstance(max_value, int)
            else "FloatSlider"
        )

        slider = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="widgets", ctx=ast.Load()),
                attr=slider_type,
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[
                ast.keyword(arg="min", value=ast.Constant(value=min_value)),
                ast.keyword(arg="max", value=ast.Constant(value=max_value)),
                ast.keyword(arg="step", value=ast.Constant(value=step)),
                ast.keyword(arg="value", value=ast.Constant(value=min_value if default_value is None else default_value)),
            ],
        )

        return slider

    def _convert_abbreviation_to_slider(self, abbreviation, default_value):
        if default_value:
            value = default_value
        else:
            if isinstance(abbreviation, ast.Num):
                value = abbreviation.n
            elif isinstance(abbreviation, ast.Constant):
                value = abbreviation.value
            else:
                raise ValueError("Invalid abbreviation type")

        min_value = -abs(value)
        max_value = 3 * abs(value)
        step = 1 if isinstance(value, int) else 0.1

        slider_type = "IntSlider" if isinstance(value, int) else "FloatSlider"

        slider = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="widgets", ctx=ast.Load()),
                attr=slider_type,
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[
                ast.keyword(arg="min", value=ast.Constant(value=min_value)),
                ast.keyword(arg="max", value=ast.Constant(value=max_value)),
                ast.keyword(arg="step", value=ast.Constant(value=step)),
                ast.keyword(arg="value", value=ast.Constant(value=value)),
            ],
        )

        return slider

    def _process_selection_slider(self, node):
        st_select_slider = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="select_slider",
            ctx=ast.Load(),
        )

        keywords = []
        description_found = any([kw.arg == "description" for kw in node.value.keywords])

        for kw in node.value.keywords:
            kw.arg = self.args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        if not description_found:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        st_select_slider_call = ast.Call(
            func=st_select_slider, args=[], keywords=keywords
        )
        new_assign = ast.Assign(targets=node.targets, value=st_select_slider_call)
        return new_assign

    def _process_file_upload(self, node):
        st_file_uploader = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="file_uploader",
            ctx=ast.Load(),
        )

        keywords = []
        description_found = any([kw.arg == "description" for kw in node.value.keywords])

        for kw in node.value.keywords:
            kw.arg = self.args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        if not description_found:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        st_file_uploader_call = ast.Call(
            func=st_file_uploader, args=[], keywords=keywords
        )
        new_assign = ast.Assign(targets=node.targets, value=st_file_uploader_call)
        self.file_upload_variables.add(node.targets[0].id)  # Store the variable name
        return new_assign

    def _process_multiselect(self, node):
        st_multiselect = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="multiselect", ctx=ast.Load()
        )

        keywords = []

        for kw in node.value.keywords:
            if node.value.func.attr == "TagsInput" and kw.arg == "allowed_tags":
                kw.arg = "options"
            elif kw.arg in self.multiselect_args_translation:
                kw.arg = self.multiselect_args_translation[kw.arg]

            if not kw.arg or kw.arg == "allow_duplicates" or kw.arg == "rows":
                continue
            keywords.append(kw)

        # Add an empty label if not specified
        if "label" not in [kw.arg for kw in keywords]:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        st_multiselect_call = ast.Call(func=st_multiselect, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_multiselect_call)
        return new_assign

    def _process_radio(self, node):
        st_radio = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="radio", ctx=ast.Load()
        )

        keywords = []
        options = None
        value_index = None

        for kw in node.value.keywords:
            translated_arg = self.dropdown_args_translation.get(kw.arg)
            if not translated_arg:
                continue

            if translated_arg == "index" and kw.arg == "value":
                value_index = kw.value.s
                continue

            if kw.arg == "options":
                options = [option.s for option in kw.value.elts]

            keywords.append(ast.keyword(arg=translated_arg, value=kw.value))

        if value_index and options:
            index = options.index(value_index)
            keywords.append(ast.keyword(arg="index", value=ast.Num(n=index)))

        st_radio_call = ast.Call(func=st_radio, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_radio_call)
        return new_assign

    def _process_checkbox(self, node):
        st_checkbox = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="checkbox", ctx=ast.Load()
        )

        keywords = []

        for kw in node.value.keywords:
            if kw.arg == "description":
                kw.arg = "label"
            if kw.arg == "indent":
                continue
            keywords.append(kw)

        st_checkbox_call = ast.Call(func=st_checkbox, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_checkbox_call)
        return new_assign

    def _process_dropdown(self, node):
        st_selectbox = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="selectbox", ctx=ast.Load()
        )

        keywords = []
        options = None
        value = None

        for kw in node.value.keywords:
            if kw.arg == "options":
                options = kw.value
            if kw.arg == "value":
                value = kw.value

            kw.arg = self.dropdown_args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        if options and value:
            index = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="list", ctx=ast.Load()),
                    attr="index",
                    ctx=ast.Load(),
                ),
                args=[options, value],
                keywords=[],
            )
            index_keyword = ast.keyword(arg="index", value=index)
            keywords.append(index_keyword)

        st_selectbox_call = ast.Call(func=st_selectbox, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_selectbox_call)
        return new_assign

    def _process_datepicker(self, node):
        st_date_input = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="date_input", ctx=ast.Load()
        )

        keywords = []
        description_found = any([kw.arg == "description" for kw in node.value.keywords])

        for kw in node.value.keywords:
            kw.arg = self.multiselect_args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        if not description_found:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        st_date_input_call = ast.Call(func=st_date_input, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_date_input_call)
        return new_assign

    def _process_time_picker(self, node):
        st_time_input = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="time_input", ctx=ast.Load()
        )

        keywords = []

        for kw in node.value.keywords:
            kw.arg = self.dropdown_args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        st_time_input_call = ast.Call(func=st_time_input, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_time_input_call)
        return new_assign

    def _process_color_picker(self, node):
        st_color_picker = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="color_picker",
            ctx=ast.Load(),
        )

        keywords = []

        for kw in node.value.keywords:
            kw.arg = self.args_translation.get(kw.arg)
            if not kw.arg:
                continue
            if kw.arg == "value" and isinstance(kw.value, ast.Constant):
                if kw.value.value in mcolors.CSS4_COLORS:
                    kw.value.value = mcolors.to_hex(kw.value.value)
            keywords.append(kw)

        st_color_picker_call = ast.Call(
            func=st_color_picker, args=[], keywords=keywords
        )
        new_assign = ast.Assign(targets=node.targets, value=st_color_picker_call)
        return new_assign

    def _process_text_input(self, node, text_type):
        st_text_input = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr=text_type, ctx=ast.Load()
        )

        keywords = []
        description_found = any([kw.arg == "description" for kw in node.value.keywords])

        for kw in node.value.keywords:
            if kw.arg == "description":
                kw.arg = "label"
            if not kw.arg:
                continue
            keywords.append(kw)

        if not description_found:
            keywords.append(ast.keyword(arg="label", value=ast.Str(s="")))

        if node.value.func.attr == "Password":
            keywords.append(ast.keyword(arg="type", value=ast.Str(s="password")))

        st_text_input_call = ast.Call(func=st_text_input, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_text_input_call)
        return new_assign

    def _process_number_input(self, node):
        st_number_input = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="number_input",
            ctx=ast.Load(),
        )

        keywords = []

        for kw in node.value.keywords:
            kw.arg = self.args_translation.get(kw.arg)
            if not kw.arg:
                continue
            keywords.append(kw)

        # Check if any of the numerical arguments are floats
        has_float = any(
            [
                isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, float)
                for kw in keywords
            ]
        )

        if has_float:
            # Convert all numerical arguments to float
            for kw in keywords:
                if isinstance(kw.value, ast.Constant) and isinstance(
                    kw.value.value, int
                ):
                    kw.value.value = float(kw.value.value)

        st_number_input_call = ast.Call(
            func=st_number_input, args=[], keywords=keywords
        )
        new_assign = ast.Assign(targets=node.targets, value=st_number_input_call)
        return new_assign

    def _process_button_call(self, call_node, on_click_callback=None):
        new_keywords = []
        icon = None
        label = None

        for kw in call_node.keywords:
            if kw.arg == "description":
                label = kw.value
            elif kw.arg == "disabled":
                new_keywords.append(ast.keyword(arg="disabled", value=kw.value))
            elif kw.arg == "tooltip":
                new_keywords.append(ast.keyword(arg="help", value=kw.value))
            elif kw.arg == "icon":
                icon = kw.value.s

        if label is None:
            label = ast.Str(s="Button")

        if icon:
            new_label = ast.BinOp(
                left=ast.Str(s=f":{icon}: "),
                op=ast.Add(),
                right=label,
            )
        else:
            new_label = label

        new_keywords.append(ast.keyword(arg="label", value=new_label))

        if on_click_callback:
            new_keywords.append(ast.keyword(arg="on_click", value=on_click_callback))

        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="st", ctx=ast.Load()), attr="button", ctx=ast.Load()
            ),
            args=[],
            keywords=new_keywords,
        )

    def _process_button(self, node):
        st_button = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()), attr="button", ctx=ast.Load()
        )

        keywords = []
        description_found = False
        supported_button_args = {
            "description": "label",
            "disabled": "disabled",
            "tooltip": "help",
        }
        icon_value = None

        for kw in node.value.keywords:
            if kw.arg == "icon":
                icon_value = kw.value.s
                continue

            if kw.arg in supported_button_args:
                kw.arg = supported_button_args[kw.arg]
            else:
                # Ignore unsupported arguments like 'value' and 'button_style'
                continue

            if kw.arg == "label":
                description_found = True
                if icon_value:
                    kw.value.s = f":{icon_value}: {kw.value.s}"

            keywords.append(kw)

        if not description_found and icon_value:
            keywords.append(
                ast.keyword(arg="label", value=ast.Str(s=f":{icon_value}:"))
            )

        st_button_call = ast.Call(func=st_button, args=[], keywords=keywords)
        new_assign = ast.Assign(targets=node.targets, value=st_button_call)
        return new_assign

    def _process_display(self, node):
        if isinstance(node.value.args[0], ast.Name):
            var_name = node.value.args[0].id
            if (
                var_name in self.transformed_variables
                or var_name in self.file_upload_variables
            ):
                return None

        st_write = ast.Attribute(
            value=ast.Name(id="st", ctx=ast.Load()),
            attr="write",
            ctx=ast.Load(),
        )
        st_write_call = ast.Call(
            func=st_write, args=node.value.args, keywords=node.value.keywords
        )
        return ast.Expr(value=st_write_call)

    def _process_import(self, node):
        if any(alias.name == "ipywidgets" for alias in node.names):
            return ast.Import(names=[ast.alias(name="streamlit", asname="st")])
        return node

    def _process_interactive(self, node):
        function_name = node.value.args[0].id
        new_statements = []

        function_def = None
        for n in self.module_body:
            if isinstance(n, ast.FunctionDef) and n.name == function_name:
                function_def = n
                break

        if not function_def:
            raise ValueError(f"Function '{function_name}' not found in the module body")

        arg_defaults = {}
        for arg, default in zip(function_def.args.args[-len(function_def.args.defaults):], function_def.args.defaults):
            arg_defaults[arg.arg] = default

        for kw in node.value.keywords:
            slider_name = kw.arg
            slider = kw.value

            default = arg_defaults.get(slider_name, None)

            default_value = default.value if isinstance(default, ast.Constant) else None

            if isinstance(slider, ast.Num) or isinstance(slider, ast.Constant):
                slider = self._convert_abbreviation_to_slider(slider, default_value)

            if isinstance(slider, ast.Tuple):
                slider = self._convert_abbreviation_tuple_to_slider(slider, default_value)

            slider_attr = slider.keywords

            label = ast.Str(s=slider_name + ":")
            keywords = []

            for attr in slider_attr:
                if attr.arg in self.args_translation:
                    keywords.append(
                        ast.keyword(
                            arg=self.args_translation[attr.arg], value=attr.value
                        )
                    )

            slider_call = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="st", ctx=ast.Load()),
                    attr="slider",
                    ctx=ast.Load(),
                ),
                args=[label],
                keywords=keywords,
            )

            slider_assign = ast.Assign(
                targets=[ast.Name(id=slider_name, ctx=ast.Store())], value=slider_call
            )
            new_statements.append(slider_assign)

        function_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id=function_name, ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(arg=kw.arg, value=ast.Name(id=kw.arg, ctx=ast.Load()))
                    for kw in node.value.keywords
                ],
            )
        )

        new_statements.append(function_call)
        return new_statements
