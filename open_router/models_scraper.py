import requests
from bs4 import BeautifulSoup
from selenium import webdriver
import yaml
import time
# Set up the webdriver
driver = webdriver.Chrome()

# Navigate to the webpage
driver.get('https://openrouter.ai/docs#quick-start')

# Wait for the webpage to load completely
time.sleep(10)

# Parse the HTML content using BeautifulSoup
soup = BeautifulSoup(driver.page_source, 'html.parser')

# Find the table with the class 'table-fixed w-full'
models_table = soup.find('table', {'class': 'table-fixed w-full'})

# Assuming each model is in a row within the table body (tbody)
model_rows = models_table.find('tbody').find_all('tr')

models_data = []
for row in model_rows:
    # Find the anchor and code tags within the row
    model_name_tag = row.find('a')
    model_id_tag = row.find('code')
    
    # Extract the text from the tags
    model_name = model_name_tag.text.strip() if model_name_tag else ""
    model_id = model_id_tag.text.strip() if model_id_tag else ""
    model_href = model_name_tag['href'] if model_name_tag else ""
    
    model_info = {
        "category": "generic",
        "datasets": "unknown",
        "icon": "",  # Placeholder for icon URL
        "last_commit_time": "",  # Placeholder for last commit time
        "license": "commercial",
        "model_creator": "",  # Placeholder for model creator
        "model_creator_link": model_href,  # Extracted href from the anchor tag
        "name": model_id,
        "quantizer": None,
        "rank": 0.0,  # Placeholder for rank
        "type": "api",
        "variants": [
            {
                "name": model_name,
                "size": "Not so much"  # Placeholder for size
            }
        ]
    }
    models_data.append(model_info)

# Convert the list of dictionaries to YAML
models_yaml = yaml.dump(models_data)

# Output the YAML or write it to a file
print(models_yaml)
with open('models.yaml', 'w') as yaml_file:
    yaml_file.write(models_yaml)
