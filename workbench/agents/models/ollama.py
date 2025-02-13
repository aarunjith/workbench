from .base_llm import BaseLLM, ModelConfig, ModelResponse
from typing import List, Dict, Any, Optional
from ..agent_messages import AgentMessage
from ...listener import ListenerMetadata
from ollama import AsyncClient
from logging import getLogger
import re
logger = getLogger(__name__)


class OllamaModel(BaseLLM):
    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        assert model_config.provider == "ollama", "Ollama provider must be ollama"
        # If requesting for JSON then we need to update the system prompt
        if model_config.response_format:
            assert isinstance(
                model_config.response_format, str
            ), "Response format must be a string"
            self.system_prompt = f"{self.system_prompt}\n\n{f'Respond in the following format only: \n{model_config.response_format}'}"
        self.model_name = self.get_ollama_name(self.model_name)
        self.client = AsyncClient()

    def get_ollama_name(self, model_name: str) -> str:
        return model_name.split("/")[1]

    def construct_tools_input(
        self, connected_listeners: List[ListenerMetadata]
    ) -> List[Dict[str, Any]]:
        if not connected_listeners:
            return []
        tools_input = [
            {
                "name": f"{listener.listener_name}__{listener.listener_id}",
                "description": listener.description,
                "input_schema": listener.input_schema,
            }
            for listener in connected_listeners
        ]
        logger.debug(f"Tools input: {tools_input}")
        return tools_input

    async def generate_response(
        self,
        messages: List[AgentMessage],
        connected_listeners: Optional[List[ListenerMetadata]] = None,
    ) -> ModelResponse:
        logger.debug(f"Messages: {messages}")
        tools_input = self.construct_tools_input(connected_listeners)
        system_prompt = self.get_system_prompt(tools_input)
        if self.system_prompt:
            system_prompt = f"{system_prompt}\n\n{self.system_prompt}"
        current_messages = [{"role": "system", "content": system_prompt}]
        messages = [*current_messages, *[message.model_dump() for message in messages]]

        response = await self.client.chat(
            messages=messages,
            model=self.model_name,
        )

        logger.debug(f"Response: {response}")
        parsed_response = self.parse_response(response)
        logger.debug(f"Parsed response: {parsed_response}")
        return parsed_response

    def get_system_prompt(self, tools_input: List[Dict[str, Any]]) -> str:
        template = """You are an expert in composing functions. You are given a question and a set of possible functions. 
        Based on the question, you will need to make one or more function/tool calls to achieve the purpose. 
        If none of the function can be used, point it out. If the given question lacks the parameters required by the function,
        also point it out. You should only return the function call in tools call sections.

        If you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]\n
        You SHOULD NOT include any other text in the response.

        Here is a list of functions in JSON format that you can invoke.\n\n{functions}\n"""
        return template.format(functions=tools_input)
    
    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        logger.debug(f"Response to parse: {response}")
        response_text = ""
        tool_use = False
        tool_name = None
        target_listener = None
        tool_args = None

        # Get the message content from the response
        if hasattr(response, "message"):
            response_text = response.message.content
            parsed_content = self.parse_content(response_text)
            if isinstance(parsed_content, list) and len(parsed_content) > 0:
                tool_use = True
                # Get the first function call
                first_call = parsed_content[0]
                function_name = first_call["name"]
                # Split function name into tool_name and target_listener if it contains "__"
                if "__" in function_name:
                    tool_name, target_listener = function_name.split("__")
                else:
                    tool_name = function_name
                tool_args = first_call["args"]

        # Get token counts from the response
        input_tokens = getattr(response, "prompt_eval_count", 0)
        output_tokens = getattr(response, "eval_count", 0)

        return ModelResponse(
            response_text=response_text,
            tool_use=tool_use,
            tool_name=tool_name,
            target_listener=target_listener,
            tool_args=tool_args,
            output_tokens=output_tokens,
            input_tokens=input_tokens,
        )

    def parse_content(self, content: str) -> List[Dict]:
        """
        Parse content string into a list of dictionaries with 'name' and 'args' keys.
        Handles multiple function calls within the same brackets, even when embedded in other text.
        
        Args:
            content (str): Input string containing function calls
            
        Returns:
            List[Dict]: List of parsed functions, where each function has:
                - name: name of the function
                - args: dictionary of function arguments
                
        Examples:
            >>> parse_content("[func1(param1='value1'), func2(param2='value2')]")
            [
                {'name': 'func1', 'args': {'param1': 'value1'}},
                {'name': 'func2', 'args': {'param2': 'value2'}}
            ]
            >>> parse_content("Here's what I'll do: [func1(param1='value1')] and that's it.")
            [
                {'name': 'func1', 'args': {'param1': 'value1'}}
            ]
        """
        results = []
        
        # Find all content within square brackets that looks like function calls
        bracket_pattern = r'\[([\w_-]+\([^]]*\)(?:\s*,\s*[\w_-]+\([^]]*\))*)\]'
        bracket_matches = re.finditer(bracket_pattern, content)
        
        for bracket_match in bracket_matches:
            function_calls_str = bracket_match.group(1)
            # Split multiple function calls within the same brackets
            function_calls = re.split(r'\s*,\s*(?=[\w_-]+\()', function_calls_str)
            
            for func_call in function_calls:
                # Pattern to match function name and arguments
                func_match = re.match(r'([\w_-]+)\((.*)\)', func_call)
                
                if func_match:
                    func_name = func_match.group(1)
                    args_str = func_match.group(2)
                    
                    # Parse arguments
                    args = {}
                    # Pattern to match key='value' pairs
                    args_pattern = r"(\w+)='([^']*)'|(\w+)=([^,\s]+)"
                    
                    arg_matches = re.findall(args_pattern, args_str)
                    for match in arg_matches:
                        if match[0]:  # Quoted value
                            key, value = match[0], match[1]
                        else:  # Unquoted value
                            key, value = match[2], match[3]
                        args[key] = value
                        
                    results.append({
                        'name': func_name,
                        'args': args
                    })
        
        if not results:
            results = content
        return results
