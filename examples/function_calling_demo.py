#!/usr/bin/env python

# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import copy
import functools
import inspect
import json
import operator
import reprlib
import sys
major = sys.version_info.major
minor = sys.version_info.minor
if int(major) != 3 or int(minor) < 8:
    raise RuntimeError(
        f"The Gradio demo requires Python >= 3.8, but your Python version is {major}.{minor}."
    )
import textwrap
import traceback

import erniebot as eb
import gradio as gr

CUSTOM_FUNC_NAME = 'custom_function'


def parse_setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8073)
    args = parser.parse_args()
    return args


def create_ui_and_launch(args):
    with gr.Blocks(
            title="ERNIE Bot SDK Function Calling Demo",
            theme=gr.themes.Soft(
                spacing_size='sm', text_size='sm')) as block:
        create_components(functions=get_predefined_functions())

    block.queue(api_open=False).launch(
        server_name="0.0.0.0", server_port=args.port)


def create_components(functions):
    func_name_list = list(map(operator.attrgetter('name'), functions))
    name2function = collections.OrderedDict(zip(func_name_list, functions))
    default_state = {'name2function': name2function, 'context': []}
    default_api_type = 'qianfan'
    default_model = 'ernie-bot-3.5'

    state = gr.State(value=default_state)
    auth_state = gr.State(value={
        'api_type': default_api_type,
        'ak': "",
        'sk': "",
    })

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Accordion(label="基础配置", open=True):
                api_type = gr.Dropdown(
                    label="API Type",
                    info=f"提供对话能力的后端平台",
                    value=default_api_type,
                    choices=['qianfan', 'aistudio'])
                access_key = gr.Textbox(
                    label="Access Key ID",
                    info="用于访问后端平台的AK，如果设置了access token则无需设置此参数",
                    type='password')
                secret_key = gr.Textbox(
                    label="Secret Access Key",
                    info="用于访问后端平台的SK，如果设置了access token则无需设置此参数",
                    type='password')
                access_token = gr.Textbox(
                    label="Access Token",
                    info="用于访问后端平台的access token，如果设置了AK、SK则无需设置此参数",
                    type='password')
                ernie_model = gr.Dropdown(
                    label="Model",
                    info=f"模型类型",
                    value=default_model,
                    choices=['ernie-bot-3.5'])
            with gr.Accordion(label="高级配置", open=False):
                top_p = gr.Slider(
                    label="Top-p",
                    info="控制采样范围，该参数越小生成结果越稳定",
                    value=0.7,
                    minimum=0,
                    maximum=1,
                    step=0.05)
                temperature = gr.Slider(
                    label="Temperature",
                    info="控制采样随机性，该参数越小生成结果越稳定",
                    value=0.95,
                    minimum=0.05,
                    maximum=1.5,
                    step=0.05)
            with gr.Accordion(label="函数信息", open=False):
                with gr.Column():
                    with gr.Tabs():
                        for function in functions:
                            create_function_tab(function)
                        with gr.Tab(label="自定义函数"):
                            custom_func_code = gr.Code(
                                label="定义",
                                value=get_custom_func_def_template(),
                                language='python',
                                interactive=True)
                            update_func_desc_btn = gr.Button("更新描述")
                            custom_func_desc = JSONCode(
                                label="描述",
                                value=to_pretty_json(
                                    get_custom_func_desc_template(),
                                    from_json=False),
                                interactive=True)
            chosen_func_names = gr.CheckboxGroup(
                label="备选函数",
                value=func_name_list,
                choices=func_name_list + [CUSTOM_FUNC_NAME])

        with gr.Column(scale=2):
            context_chatbot = gr.Chatbot(label="对话历史")
            input_text = gr.Textbox(label="消息内容", placeholder="请输入...")
            with gr.Row():
                clear_btn = gr.Button("重置对话")
                regen_btn = gr.Button("重新生成")
                send_text_btn = gr.Button("发送文本")
            func_call_accord = gr.Accordion(label="函数调用", open=False)
            with func_call_accord:
                with gr.Row():
                    with gr.Column():
                        func_name = gr.Textbox(label="函数名称")
                        func_in_params = JSONCode(label="请求参数")
                        func_out_params = JSONCode(
                            label="响应参数", interactive=False)
                    with gr.Column():
                        call_func_btn = gr.Button("调用函数")
                        send_res_btn = gr.Button("发送调用结果")
                        reset_func_btn = gr.Button("重置函数调用信息")
        with gr.Column(scale=1):
            raw_context_json = gr.JSON(label="原始对话上下文信息")

        api_type.change(
            update_api_type,
            inputs=[
                auth_state,
                api_type,
            ],
            outputs=[
                auth_state,
                access_key,
                secret_key,
            ],
        )
        access_key.change(
            make_state_updater(
                key='ak', strip=True),
            inputs=[
                auth_state,
                access_key,
            ],
            outputs=auth_state,
        )
        secret_key.change(
            make_state_updater(
                key='sk', strip=True),
            inputs=[
                auth_state,
                secret_key,
            ],
            outputs=auth_state,
        )
        access_token.change(
            make_state_updater(
                key='access_token', strip=True),
            inputs=[
                auth_state,
                access_token,
            ],
            outputs=auth_state,
        )

        input_text.submit(
            generate_response_for_text,
            inputs=[
                state,
                chosen_func_names,
                auth_state,
                ernie_model,
                input_text,
                top_p,
                temperature,
            ],
            outputs=[
                state,
                input_text,
                context_chatbot,
                raw_context_json,
                func_name,
                func_in_params,
                func_out_params,
                func_call_accord,
            ],
        )
        clear_btn.click(
            reset_conversation,
            inputs=state,
            outputs=[
                state,
                input_text,
                context_chatbot,
                raw_context_json,
                func_name,
                func_in_params,
                func_out_params,
            ],
            show_progress=False,
        )
        regen_btn.click(
            regenerate_response,
            inputs=[
                state,
                chosen_func_names,
                auth_state,
                ernie_model,
                top_p,
                temperature,
            ],
            outputs=[
                state,
                input_text,
                context_chatbot,
                raw_context_json,
                func_name,
                func_in_params,
                func_out_params,
                func_call_accord,
            ],
        )
        send_text_btn.click(
            generate_response_for_text,
            inputs=[
                state,
                chosen_func_names,
                auth_state,
                ernie_model,
                input_text,
                top_p,
                temperature,
            ],
            outputs=[
                state,
                input_text,
                context_chatbot,
                raw_context_json,
                func_name,
                func_in_params,
                func_out_params,
                func_call_accord,
            ],
        )

        custom_func_code.change(
            remove_old_custom_function,
            inputs=[
                state,
                chosen_func_names,
            ],
            outputs=[
                state,
                chosen_func_names,
            ],
            show_progress=False,
        )
        custom_func_desc.change(
            remove_old_custom_function,
            inputs=[
                state,
                chosen_func_names,
            ],
            outputs=[
                state,
                chosen_func_names,
            ],
            show_progress=False,
        )
        update_func_desc_btn.click(
            try_update_custom_func_desc,
            inputs=[
                custom_func_code,
                custom_func_desc,
            ],
            outputs=custom_func_desc,
        )
        chosen_func_names.change(
            try_update_candidates,
            inputs=[
                state,
                chosen_func_names,
                custom_func_code,
                custom_func_desc,
            ],
            outputs=[
                state,
                chosen_func_names,
            ],
        )

        call_func_btn.click(
            call_function,
            inputs=[
                state,
                chosen_func_names,
                func_name,
                func_in_params,
            ],
            outputs=func_out_params,
        )
        send_res_btn.click(
            generate_response_for_function,
            inputs=[
                state,
                chosen_func_names,
                auth_state,
                ernie_model,
                func_name,
                func_out_params,
                top_p,
                temperature,
            ],
            outputs=[
                state,
                input_text,
                context_chatbot,
                raw_context_json,
                func_name,
                func_in_params,
                func_out_params,
            ],
        )
        reset_func_btn.click(
            lambda: (None, None, None),
            outputs=[
                func_name,
                func_in_params,
                func_out_params,
            ],
            show_progress=False,
        )


def create_function_tab(function):
    with gr.Tab(label=function.name):
        with gr.Column():
            gr.Code(
                label="定义",
                value=get_source_code(function.func),
                language='python',
                interactive=False)
            JSONCode(
                label="描述",
                value=to_pretty_json(
                    function.desc, from_json=False),
                interactive=False)


def make_state_updater(key, *, strip=False):
    def _update_state(state, val):
        if strip:
            val = val.strip()
        state[key] = val
        return state

    return _update_state


def update_api_type(auth_state, api_type):
    auth_state['api_type'] = api_type
    if api_type == 'qianfan':
        return auth_state, gr.update(visible=True), gr.update(visible=True)
    elif api_type == 'aistudio':
        return auth_state, gr.update(visible=False), gr.update(visible=False)


def remove_old_custom_function(state, candidates):
    state['name2function'].pop(CUSTOM_FUNC_NAME, None)
    if CUSTOM_FUNC_NAME in candidates:
        candidates.remove(CUSTOM_FUNC_NAME)
    return state, candidates


def try_update_custom_func_desc(custom_func_code, custom_func_desc_str):
    try:
        func = code_to_function(custom_func_code, CUSTOM_FUNC_NAME)
        sig = inspect.signature(func)
        custom_func_desc = json_to_obj(custom_func_desc_str)
        new_params_desc = get_custom_func_desc_template()['parameters']
        for param in sig.parameters.values():
            name = param.name
            if name in custom_func_desc['parameters']['properties']:
                param_desc = custom_func_desc['parameters']['properties'][name]
            else:
                param_desc = {}
            if param.kind in (param.POSITIONAL_ONLY, param.VAR_POSITIONAL,
                              param.VAR_KEYWORD):
                raise gr.Error(
                    "函数中不可包含positional-only、var-positional或var-keyword参数")
            if param.default is not param.empty:
                param_desc['default'] = param.default
            else:
                if 'default' in param_desc:
                    del param_desc['default']
            if param.kind == param.POSITIONAL_OR_KEYWORD and param.default is param.empty:
                if 'required' not in new_params_desc:
                    new_params_desc['required'] = []
                new_params_desc['required'].append(name)
            new_params_desc['properties'][name] = param_desc
        custom_func_desc['parameters'] = new_params_desc
    except Exception as e:
        traceback.print_exc()
        gr.Warning(f"更新函数描述失败，错误信息如下：{str(e)}")
        return gr.update()
    else:
        return to_pretty_json(custom_func_desc)


def try_update_candidates(state, candidates, custom_func_code,
                          custom_func_desc_str):
    if CUSTOM_FUNC_NAME in candidates:
        try:
            custom_function = make_custom_function(custom_func_code,
                                                   custom_func_desc_str)
        except Exception as e:
            traceback.print_exc()
            gr.Warning(f"自定义函数的定义或描述中存在错误，无法将其添加为候选函数。错误信息如下：{str(e)}")
            # HACK: Add a time delay so that the warning can be read.
            import time
            time.sleep(3)
            candidates.remove(CUSTOM_FUNC_NAME)
        else:
            state['name2function'][CUSTOM_FUNC_NAME] = custom_function
    return state, candidates


def make_custom_function(code, desc_str):
    func = code_to_function(code, CUSTOM_FUNC_NAME)
    if func.__name__ != CUSTOM_FUNC_NAME:
        raise gr.Error(f"在自定义函数的定义中，必须将函数名称设置为{repr(CUSTOM_FUNC_NAME)}")
    desc = json_to_obj(desc_str)
    if desc['name'] != CUSTOM_FUNC_NAME:
        raise gr.Error(f"在自定义函数的描述中，必须将函数名称设置为{repr(CUSTOM_FUNC_NAME)}")
    return make_function(func, desc, name=CUSTOM_FUNC_NAME)


def generate_response_for_text(
        state,
        candidates,
        auth_config,
        ernie_model,
        content,
        top_p,
        temperature,
):
    if content.strip() == '':
        raise gr.Error("输入不能为空，请在重置对话后重试")
    content = content.strip().replace('<br>', '\n')
    message = {'role': 'user', 'content': content}
    return generate_response(
        state=state,
        candidates=candidates,
        auth_config=auth_config,
        ernie_model=ernie_model,
        message=message,
        top_p=top_p,
        temperature=temperature,
    )


def generate_response_for_function(
        state,
        candidates,
        auth_config,
        ernie_model,
        func_name,
        func_res,
        top_p,
        temperature,
):
    if func_name.strip() == '':
        raise gr.Error("函数名称不能为空，请在重置对话后重试")
    func_name = func_name.strip()
    message = {
        'role': 'function',
        'name': func_name,
        'content': to_compact_json(
            func_res, from_json=True)
    }
    return generate_response(
        state=state,
        candidates=candidates,
        auth_config=auth_config,
        ernie_model=ernie_model,
        message=message,
        top_p=top_p,
        temperature=temperature,
    )


def regenerate_response(
        state,
        candidates,
        auth_config,
        ernie_model,
        top_p,
        temperature,
):
    context = state['context']
    if len(context) < 2:
        raise gr.Error("请至少进行一轮对话")
    old_context = copy.copy(context)
    context.pop()
    user_message = context.pop()
    kwargs = dict(
        state=state,
        candidates=candidates,
        auth_config=auth_config,
        ernie_model=ernie_model,
        top_p=top_p,
        temperature=temperature,
    )
    try:
        if user_message['role'] == 'function':
            kwargs['func_name'] = user_message['name']
            kwargs['func_res'] = user_message['content']
            return generate_response_for_function(**kwargs)
        elif user_message['role'] == 'user':
            kwargs['content'] = user_message['content']
            return generate_response_for_text(**kwargs)
        else:
            raise gr.Error("消息中的`role`不正确")
    except Exception as e:
        state['context'] = old_context
        traceback.print_exc()
        raise gr.Error(f"重新生成结果失败，原因如下：{str(e)}") from e


def reset_conversation(state):
    state['context'].clear()
    return state, None, None, None, None, None, None


def generate_response(
        state,
        candidates,
        auth_config,
        ernie_model,
        message,
        top_p,
        temperature,
):
    if auth_config['ak'] == '' or auth_config['sk'] == '':
        raise gr.Error("需要填写正确的AK/SK，不能为空")

    model = 'ernie-bot-3.5' if (ernie_model is None or
                                ernie_model.strip() == '') else ernie_model
    context = copy.copy(state['context'])
    context.append(message)
    name2function = state['name2function']
    functions = [name2function[name].desc for name in candidates]
    data = {
        'messages': context,
        'top_p': top_p,
        'temperature': temperature,
        'functions': functions
    }

    response = create_chat_completion(
        _config_=auth_config, model=model, **data, stream=False)

    if hasattr(response, 'function_call'):
        function_call = response.function_call
        context.append({
            'role': 'assistant',
            'content': None,
            'function_call': function_call
        })
        func_name = function_call['name']
        func_args = to_pretty_json(function_call['arguments'], from_json=True)
        accord_update = gr.update(open=True)
    else:
        context.append({'role': 'assistant', 'content': response.result})
        func_name = None
        func_args = None
        accord_update = gr.update()
    history = get_history(context)
    state['context'] = context
    return state, None, history, context, func_name, func_args, None, accord_update


def get_history(context):
    # TODO: Cache history and make incremental updates.
    history = []

    for turn_idx in range(0, len(context), 2):
        user_message = context[turn_idx]
        pair = []
        if user_message['role'] == 'function':
            pair.append(
                f"**【函数调用】** 我调用了函数`{user_message['name']}`，函数的返回结果如下：\n```\n{to_pretty_json(user_message['content'], from_json=True)}\n```"
            )
        elif user_message['role'] == 'user':
            pair.append(user_message['content'])
        else:
            raise gr.Error("消息中的`role`不正确")

        assistant_message = context[turn_idx + 1]
        if 'function_call' in assistant_message:
            function_call = assistant_message['function_call']
            pair.append(
                f"**【函数调用】** {function_call['thoughts']}\n我建议调用函数`{function_call['name']}`，传入如下参数：\n```\n{to_pretty_json(function_call['arguments'], from_json=True)}\n```"
            )
        else:
            pair.append(assistant_message['content'])

        assert len(pair) == 2
        history.append(pair)

    return history


def call_function(state, candidates, func_name, func_args):
    name2function = state['name2function']
    if not func_name in name2function:
        raise gr.Error(f"函数`{func_name}`不存在")
    if not func_name in candidates:
        raise gr.Error(f"函数`{func_name}`不是候选函数")
    func = name2function[func_name].func
    func_args = json_to_obj(func_args)
    if not isinstance(func_args, dict):
        raise gr.Error(f"无法将{reprlib.repr(func_args)}解析为字典")
    res = func(**func_args)
    return to_pretty_json(res, from_json=False)


JSONCode = functools.partial(gr.Code, language='json')

Function = collections.namedtuple('Function', ['name', 'func', 'desc'])


def get_predefined_functions():
    functions = []

    def add(a, b):
        return {'result': a + b}

    add_desc = {
        'name': 'add',
        'description': "计算两数之和",
        'parameters': {
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'integer',
                },
                'b': {
                    'type': 'integer',
                },
            },
            'required': [
                'a',
                'b',
            ],
        },
        'responses': {
            'type': 'object',
            'properties': {
                'result': {
                    'type': 'integer',
                    'description': "两数之和",
                },
            },
        },
    }

    functions.append(make_function(add, add_desc))

    def get_current_date(breakup=False):
        from datetime import date
        today = date.today()
        ret = {}
        if breakup:
            ret['year'] = today.year
            ret['month'] = today.month
            ret['day'] = today.day
        else:
            ret['date'] = str(today)
        return ret

    get_current_date_desc = {
        'name': 'get_current_date',
        'description': "获取当日日期",
        'parameters': {
            'type': 'object',
            'properties': {
                'breakup': {
                    'type': 'boolean',
                    'description': "是否分开返回年、月、日信息",
                    'default': False,
                },
            },
        },
        'responses': {
            'type': 'object',
            'properties': {
                'date': {
                    'type': 'string',
                    'description': "完整日期，如'2023-09-13'"
                },
                'year': {
                    'type': 'integer',
                },
                'month': {
                    'type': 'integer',
                },
                'day': {
                    'type': 'integer',
                },
            },
        },
    }

    functions.append(make_function(get_current_date, get_current_date_desc))

    return functions


def get_custom_func_def_template():
    indent = 2
    return f"def {CUSTOM_FUNC_NAME}():\n{' '*indent}# Write your code here"


def get_custom_func_desc_template():
    return {
        'name': CUSTOM_FUNC_NAME,
        'description': "",
        'parameters': {
            'type': 'object',
            'properties': {},
        },
        'responses': {
            'type': 'object',
            'properties': {},
        },
    }


def code_to_function(code, func_name):
    code = compile(code, '<string>', 'exec')
    co_names = code.co_names
    if len(co_names) != 1 or co_names[0] != func_name:
        raise gr.Error(f"只允许定义一个函数，函数名为{repr(func_name)}")
    locals_ = {}
    exec(code, {'__builtins__': {}}, locals_)
    func = locals_[func_name]
    return func


def get_source_code(func):
    code = inspect.getsource(func)
    return textwrap.dedent(code)


def make_function(func, desc, *, name=None):
    if name is None:
        name = func.__name__
    return Function(name=name, func=func, desc=desc)


def create_chat_completion(*args, **kwargs):
    try:
        response = eb.ChatCompletion.create(*args, **kwargs)
    except eb.errors.EBError as e:
        traceback.print_exc()
        raise gr.Error(f"请求失败，错误信息如下：{str(e)}") from e
    return response


def json_to_obj(str_):
    try:
        return json.loads(str_)
    except (TypeError, json.JSONDecodeError) as e:
        raise gr.Error(f"无法以JSON格式解码{reprlib.repr(str_)}") from e


def obj_to_json(obj, **kwargs):
    try:
        return json.dumps(obj, **kwargs)
    except TypeError as e:
        raise gr.Error(f"无法将{reprlib.repr(obj)}编码为JSON") from e


def to_compact_json(obj, *, from_json=False):
    if from_json:
        obj = json_to_obj(obj)
    return obj_to_json(obj, separators=(',', ':'))


def to_pretty_json(obj, *, from_json=False):
    if from_json:
        obj = json_to_obj(obj)
    return obj_to_json(obj, sort_keys=False, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    args = parse_setup_args()
    create_ui_and_launch(args)
