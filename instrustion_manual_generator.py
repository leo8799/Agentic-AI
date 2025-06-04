from google import genai
import json
import os
from typing import Optional, List, Dict, Literal
from json.decoder import JSONDecodeError
import logging

class InstructionManualGenerator:
    def __init__(
        self,
        api_key: str,
        task_goal: str,
        results: List[Dict],
        logger: logging.Logger,
        instruction_format: Literal["text_steps", "json_blocks"] = "text_steps",
    ):
        """
        Initialize the instruction manual generator for WebVoyager tasks.

        Args:
            api_key (str): Gemini API key.
            task_goal (str): The task goal string (e.g., identifying the professor of a course).
            results (List[Dict]): A list of dictionaries containing retrieved results.
            logger: Logging object
            instruction_format (Literal["text_steps", "json_blocks"]): The desired output format for the manual.
                - "text_steps": Generates a human-readable step-by-step manual.
                - "json_blocks": Outputs a structured JSON manual with descriptions and sources.
        """
        self.client = genai.Client(api_key=api_key)
        self.task_goal = task_goal
        self.results = results
        self.instruction_format = instruction_format
        self.logger = logger

    def _generate_prompt(self):
        """
        Generates the prompt for Gemini's model based on task goal and results.
        :return: The formatted prompt string.
        """
        prompt = f"""
You are a professional technical document assistant for WebVoyager, a web browsing agent. Your task is to filter relevant information from the provided retrieval results based on the given task goal and compile it into a structured instruction manual with actionable, numbered steps to guide the agent in completing the task.

### Task Goal:
{self.task_goal}

### Retrieval Results Example:
Each result contains:
- content: (The main information retrieved)
- metadata: (Additional information about the content)
- similarity: (The relevance score of this result to the query)

### Relevance Criteria:
- The goal is to compile an **instruction manual** that provides actionable steps to achieve the task.
- A result is **relevant** if it:
  - Contains keywords or terminology directly related to any possible approach for completing the task goal
  - Includes step-by-step instructions, procedures, or operations that could contribute to task completion
  - Describes key functions, tools, or settings that might be useful for the task
  - Contains configuration details, system behaviors, or technical information that could aid in achieving the goal
  - Provides partial but useful information, even if it only addresses one aspect of the task
  - Mentions alternative methods or approaches that could accomplish the same goal
- A result is **not relevant** if it:
  - Contains no keywords or terminology related to any approach for completing the task
  - Provides only general theoretical concepts without practical application
  - Is completely unrelated to the task goal or any of its components

### Filtering Process:
1. **Identify Relevant Information**  
   - Consider whether the retrieved content helps in accomplishing the task through ANY possible approach
   - Even if the information describes just one possible method or only a portion of a method, include it
   - If a section contains even one relevant keyword or concept related to task completion, consider it relevant
   - Pay attention to the similarity score as it indicates the relevance of the content

2. **Structured Output**  
   - Organize the relevant information into a step-by-step instruction manual
   - Each step must be actionable, clearly described, and numbered sequentially
   - Use action-oriented language (e.g., "Click the search button," "Type 'query' into the textbox") to ensure clarity
   - If multiple methods are available, present them as alternative approaches with clear labels (e.g., "Method 1: Step 1")
   - For irrelevant results, provide a clear explanation of why they do not contribute to the task goal

### Output Format:
Return a string containing the structured manual with numbered steps. Each step should be concise and actionable. Format as follows:
```
Task Goal: {self.task_goal}
Steps:
1. [Actionable step description]
2. [Actionable step description]
...

source: [The source of the information from metadata]
```

### Example:
For a task like "Search for the latest news on climate change":
```
Task Goal: Search for the latest news on climate change
Steps:
1. Open your web browser and navigate to www.google.com.
2. Type 'climate change latest news' into the search bar and press Enter.
3. Click on a news article from a reputable source like BBC or Reuters.
```

### Retrieval Results
{json.dumps(self.results, ensure_ascii=False, indent=2)}

Please reason step by step and ensure the manual is structured with clear, actionable steps tailored for a web browsing agent.
"""

        if self.instruction_format == "json_blocks":
            prompt = f"""
You are a professional technical document assistant. Your task is to filter the relevant information from the provided retrieval results based on the given task goal and compile it into an instruction manual.

### Task Goal:
{self.task_goal}

### Retrieval Results Example:
Each result contains:
- content: (The main information retrieved)
- metadata: (Additional information about the content)
- similarity: (The relevance score of this result to the query)

### Relevance Criteria:
- The goal is to compile an **instruction manual** that provides actionable steps to achieve the task.
- A result is **relevant** if it:
  - Contains keywords or terminology directly related to any possible approach for completing the task goal
  - Includes step-by-step instructions, procedures, or operations that could contribute to task completion
  - Describes key functions, tools, or settings that might be useful for the task
  - Contains configuration details, system behaviors, or technical information that could aid in achieving the goal
  - Provides partial but useful information, even if it only addresses one aspect of the task
  - Mentions alternative methods or approaches that could accomplish the same goal
- A result is **not relevant** if it:
  - Contains no keywords or terminology related to any approach for completing the task
  - Provides only general theoretical concepts without practical application
  - Is completely unrelated to the task goal or any of its components

### Filtering Process:
1. **Identify Relevant Information**
   - Consider whether the retrieved content helps in accomplishing the task through ANY possible approach
   - Even if the information describes just one possible method or only a portion of a method, include it
   - If a section contains even one relevant keyword or concept related to task completion, consider it relevant
   - Pay attention to the similarity score as it indicates the relevance of the content

2. **Structured Output**
   - Format relevant results in JSON, including the title, description, and source
   - For irrelevant results, provide a clear explanation of why they do not contribute to the task goal

### Retrieval Results
{json.dumps(self.results, ensure_ascii=False, indent=2)}

### Output Format:
Please output the results in the following JSON format:
```json
{{
    "manual": [
        {{
            "title": "Relevant Title",
            "description": "Operation steps filtered and compiled based on the task goal from the retrieved content",
            "source": "Source of the information from metadata"
        }}
    ],
    "irrelevant_explanations": [
        {{
            "section": "Title of the irrelevant section",
            "reason": "Explanation of why this result is not relevant"
        }}
    ]
}}
```
"""
        return prompt

    def _call_gemini(self, prompt: str) -> str:
        """
        Call Gemini API with the provided prompt and return the response.

        Args:
            prompt (str): The generated prompt string.

        Returns:
            str: The response from Gemini API.
        """
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=genai.types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=10000,
                )
            )
            return response.text
        except Exception as e:
            self.logger.error(f"Error calling Gemini API: {str(e)}")
            raise

    def generate_instruction_manual(self) -> str:
        """
        Generates a structured instruction manual by filtering relevant information from the retrieval results
        based on the defined task goal.

        This method works by:
        1. Generating a prompt using the task goal and retrieved content.
        2. Sending the prompt to the Gemini API via `_call_gemini()` to obtain a response.
        3. Handling the response based on the selected `instruction_format` (default: "text_steps"):
           - If `instruction_format` is "text_steps" (default), the method returns a free-form,
             step-by-step instruction manual directly from the model response.
           - If `instruction_format` is "json_blocks", the method parses the JSON response and converts each entry
             (including title, description, and source) into a readable manual string.

        Returns:
            str: A formatted instruction manual string, either as:
                - A step-by-step plain-text guide (if `instruction_format` is "text_steps"), or
                - A structured set of entries parsed from JSON, including title, description, and source (if `instruction_format` is "json_blocks").
        """
        prompt = self._generate_prompt()
        response_text = self._call_gemini(prompt)

        if self.instruction_format == "json_blocks":
            try:
                response_text = response_text.replace("```json", "").replace("```", "")
                response = json.loads(response_text)
                manual_obj = response["manual"]

                manual_str = "\n\n".join(
                    f"title: {entry['title']}\ndescription: {entry['description']}\nsource: {entry['source']}"
                    for entry in manual_obj
                )
                return manual_str

            except JSONDecodeError as e:
                self.logger.warning(f"[JSONDecodeError] Failed to parse response: {e}")
            except (KeyError, TypeError) as e:
                self.logger.warning(f"[FormatError] Missing expected fields in JSON response: {e}")

            return ""

        else:
            return response_text


# Example Usage
if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    # Get API key from environment variable
    api_key = "AIzaSyCw2cQTJNLAWCJYPlEvuvKV73Oa3NhZhwo"

    task_goal = "查詢資訊工程學系碩士班的課程中，AI代理系統之設計與開發這門課的授課教授是誰?"
    results = [
        {"section": "Course Information",
         "content": "The course 'AI Agent System Design and Development' is taught by Professor Zhang.",
         "source": "University Course Announcement"},
        {"section": "University News", "content": "The university is promoting intelligent course development...",
         "source": "University News Website"},
        {"section": "Student Forum", "content": "Does anyone know who teaches the AI agent system course?",
         "source": "Student Forum"}
    ]

    # Instantiate the class and generate the manual
    manual_generator = InstructionManualGenerator(
        api_key=api_key,
        task_goal=task_goal,
        results=results,
        logger=logger
    )
    manual = manual_generator.generate_instruction_manual()

    # Print the resulting manual
    print(manual)