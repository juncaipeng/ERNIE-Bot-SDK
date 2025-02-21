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

import enum

from . import errors

__all__ = ['APIType', 'convert_str_to_api_type']


class APIType(enum.Enum):
    QIANFAN = 1
    YINIAN = 2
    AISTUDIO = 3


def convert_str_to_api_type(api_type_str: str) -> APIType:
    s = api_type_str.lower()
    if s == 'qianfan':
        return APIType.QIANFAN
    elif s == 'yinian':
        return APIType.YINIAN
    elif s in ('aistudio', 'ai_studio'):
        return APIType.AISTUDIO
    else:
        raise errors.UnsupportedAPITypeError(
            f"{repr(api_type_str)} cannot be recognized as an API type.")
