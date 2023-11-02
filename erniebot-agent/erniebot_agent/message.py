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


class Message:
    def __init__(self):
        self.content = ''
    
    @property
    def type(self) -> str:
        raise NotImplementedError


class HumanMessage(Message):
    """A Message from a human."""
    
    def __init__(self, content):
        super().__init__()
        self.content = content

    @property
    def type(self) -> str:
        return "human"


class AIMessage(Message):
    """A Message from an AI."""
    
    def __init__(self, content):
        super().__init__()
        self.content = content

    @property
    def type(self) -> str:
        return "ai"