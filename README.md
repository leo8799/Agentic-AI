## Introduction

This repository is based on [WebVoyager](https://arxiv.org/abs/2401.13919), a Large Multimodal Model (LMM) powered web agent capable of completing user instructions end-to-end by interacting with real-world websites. We have modified and extended WebVoyager to enhance its functionality and improve its interaction capabilities.

Github URL: https://github.com/leo8799/Agentic-AI.git

### **Key Modifications:**
- **New "Select" Action Support**:  
  - Added a new `select` action in `prompt.py` to enable the agent to interact with dropdown menus.  
  - Implemented the `exec_action_select` function using Selenium to directly modify selected values in dropdown menus.  

- **API Migration from OpenAI to Gemini**:  
  - Replaced OpenAI's API with Gemini API for better performance and cost efficiency.  
  - Refactored the entire project to accommodate differences in JSON response format.  
  - Adjusted key mappings in the response structure (`content` → `parts`). 

- **Self-Reflection:** 
  - Add a Reflection Agent to evaluate the Agent's Thought and Action.
  - Record the Main Agent's and Reflection Agent's Trajectory. 

- **New Text Generation Features**:
  - Added `generatetext` action to generate literature summaries using RAG.
  - Implemented automatic PDF processing and storage in vector database.

- **Vector Database Integration**:
  - Automatic PDF storage in vector database for efficient retrieval.
  - Support for arXiv PDF processing and indexing.
  - Enhanced RAG capabilities for text generation and manual creation.

- **Instruction Manual Generation**:
  - Implemented task-based manual generation using RAG.
  - Generates structured planning guides for WebVoyager.
  - Integrates with vector database for relevant information retrieval.

These modifications improve WebVoyager's ability to handle complex web interactions and ensure seamless integration with new API structures.


## Setup Environment

We use Selenium to build the online web browsing environment. 
 - Make sure you have installed Chrome. (Using the latest version of Selenium, there is no need to install ChromeDriver.)
 - If you choose to run your code on a Linux server, we recommend installing chromium. (eg, for CentOS: ```yum install chromium-browser```) 
 - Create a conda environment for WebVoyager and install the dependencies.
    ```bash
    conda create -n Agentic_AI python=3.10
    conda activate Agentic_AI
    pip install -r requirements.txt
    ```

## Running

### Running Agentic AI
After setting up the environment, you can start running. 

 1. Copy the examples you want to test into `data/tasks_test.jsonl`. For Booking and Google Flights tasks, please manually update the date in the task if it is outdated.
 2. Modify the api_key in `run.sh` 

You can run the project with the following command:
```shell 
python run.py --test_file ./data/tasks_test.jsonl --api_key "your_api" --max_iter 15 --max_attached_imgs 3 --temperature 1 --seed 42 --start_maximized --trajectory --error_max_reflection_iter 3
```

### Parameters

General:
- `--test_file`: The task file to be evaluated. Please refer to the format of the data file in the `data`.
- `--max_iter`: The maximum number of online interactions for each task. Exceeding max_iter without completing the task means failure.
- `--api_key`: Your OpenAI API key.
- `--output_dir`: We should save the trajectory of the web browsing.
- `--download_dir`: Sometimes Agent downloads PDF files for analysis.
- `--trajectory`: Stored the trajectory
- `--error_max_reflection_iter`: Number of reflection restarts allowed when exceeding max_iter


Model:
- `--api_model`: The agent that receives observations and makes decisions. In our experiments, we use `gpt-4-vision-preview`. For text-only setting, models without vision input can be used, such as `gpt-4-1106-preview`.
- `seed`: This feature is in Beta according to the OpenAI [Document](https://platform.openai.com/docs/api-reference/chat). 
- `--temperature`: To control the diversity of the model, note that setting it to 0 here does not guarantee consistent results over multiple runs.
- `--max_attached_imgs`: We perform context clipping to remove outdated web page information and only keep the most recent k screenshots.
- `--text_only`: Text only setting, observation will be accessibility tree.

Web navigation:
- `--headless`: The headless model does not explicitly open the browser, which makes it easier to deploy on Linux servers and more resource-efficient. Notice: headless will affect the **size of the saved screenshot**, because in non-headless mode, there will be an address bar.
- `--save_accessibility_tree`: Whether you need to save the Accessibility Tree for the current page. We mainly refer to [WebArena](https://github.com/web-arena-x/webarena) to build the Accessibility Tree.
- `--force_device_scale`: Set device scale factor to 1. If we need accessibility tree, we should use this parameter.
- `--window_width`: Width, default is 1024.
- `--window_height`: Height, default is 768. (1024 * 768 image is equal to 765 tokens according to [OpenAI pricing](https://openai.com/pricing).)
- `--start_maximized`: Maximized the browser's width and height.
- `--fix_box_color`: We utilize [GPT-4-ACT](https://github.com/ddupont808/GPT-4V-Act), a Javascript tool to extracts the interactive elements based on web element types and then overlays bounding boxes. This option fixes the color of the boxes to black. Otherwise it is random.

### Develop Your Prompt

Prompt optimisation is a complex project which directly affects the performance of the Agent. You can find the system prompt we designed in `prompts.py`. 

The prompt we provide has been tweaked many times, but it is not perfect, and if you are interested, you can **do your own optimisation** without compromising its generality (i.e. not giving specific instructions for specific sites in the prompt). If you just need the Agent for some specific websites, then giving specific instructions is fine.

If you want to add Action to the prompt, or change the Action format, it is relatively easy to change the code. You can design your own `extract_information` function to parse the model's output and modify `run.py` to add or modify the way of action execution.

