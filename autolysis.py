import subprocess
import sys

# Function to install dependencies if missing
    

# List of required packages
required_packages = ["pandas", "seaborn", "matplotlib", "requests"]

# Install any missing packages
for package in required_packages:
    try:
        __import__(package)
    except ImportError:

        print(f"{package} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Your existing code follows here


import os
import sys
import argparse
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import requests
import json

# Constants
OUTPUT_DIR = "./analysis_results"
PNG_SIZE = (512, 512)  # Low-resolution image size for LLM efficiency
DPI = 100
SAMPLE_SIZE = 50  # Limit rows sent to the LLM for summaries
LLM_API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
LLM_MODEL = "gpt-4o-mini"

# Ensure the environment variable for AI Proxy token is set
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
if not AIPROXY_TOKEN:
    print("Error: AIPROXY_TOKEN environment variable not set.")
    sys.exit(1)


def load_dataset(file_path):
    """Load a dataset and handle encoding issues."""
    try:
        return pd.read_csv(file_path)
    except UnicodeDecodeError:
        print(f"Error: Encoding issue with {file_path}. Trying ISO-8859-1.")
        return pd.read_csv(file_path, encoding="ISO-8859-1")
    except Exception as e:
        print(f"Error loading file {file_path}: {e}")
        return None


def analyze_data(df):
    """Perform basic EDA and return summaries."""
    numeric_columns = df.select_dtypes(include=["number"]).columns
    analysis = {
        "columns": list(df.columns),
        "dtypes": df.dtypes.apply(str).to_dict(),
        "summary_stats": df.describe(include="all").to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "correlations": df[numeric_columns].corr().to_dict() if len(numeric_columns) > 1 else {},
    }
    return analysis


def generate_visualizations(df, output_dir):
    """Generate visualizations and save them as low-res PNGs."""
    os.makedirs(output_dir, exist_ok=True)
    numeric_columns = df.select_dtypes(include=["number"]).columns
    images = []

    # Correlation heatmap
    if len(numeric_columns) > 1:
        corr = df[numeric_columns].corr()
        plt.figure(figsize=(8,8))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", cbar=True)
        plt.title("Correlation Heatmap")
        corr_path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.savefig(corr_path, dpi=DPI)
        plt.close()
        images.append(corr_path)

    # Distribution plots
    for col in numeric_columns:
        plt.figure(figsize=(6, 6))
        sns.histplot(df[col], kde=True)
        plt.title(f"Distribution of {col}")
        dist_path = os.path.join(output_dir, f"{col}_distribution.png")
        plt.savefig(dist_path, dpi=DPI)
        plt.close()
        images.append(dist_path)

    return images


def ask_llm_for_insights(analysis_summary):
    # """Ask the LLM to generate insights and narrative."""
    try:
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a data analyst. Provide detailed narrative based on analysis."},
                {"role": "user", "content": f"""
I analyzed a dataset with the following details:
Columns and Types: {analysis_summary['columns']}
Missing Values: {analysis_summary['missing_values']}
Summary Statistics: {json.dumps(analysis_summary['summary_stats'])}
Correlations: {json.dumps(analysis_summary['correlations'])} 

I have also generated visualizations saved as low-resolution PNGs for correlation heatmap and distributions.
Please:
1. Summarize the dataset and analysis as a narrative.
2. Highlight key insights and potential implications.
                """}
            ],
        }
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"LLM API Error: {response.status_code} - {response.text}")
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error generating narrative: {e}"



def save_readme(narrative, images, output_dir,analysis):
    """Save the narrative and embed visualizations in README.md."""
    dtype_table = """
| Column Name           | Data Type       |
|-----------------------|-----------------|
    """
    for col, dtype in analysis["dtypes"].items():
        dtype_table += f"\n| {col:<23} | {dtype:<15} |\n\n"
    readme_path = os.path.join(output_dir, "README.md")
    with open(readme_path, "w") as f:
        f.write("# Dataset Analysis Report\n\n")
        f.write(dtype_table + "\n\n")
        f.write(narrative + "\n\n")
        f.write("## Visualizations\n")
        for img in images:
            img_name = os.path.basename(img)
            f.write(f"### {img_name}\n")
            f.write(f"![{img_name}]({img_name})\n\n")
    return readme_path


def process_dataset(file_path):
    """Process a single dataset: analyze, visualize, and generate a narrative."""
    print(f"Processing {file_path}...")
    df = load_dataset(file_path)
    if df is None:
        return None

    # Create a directory for the dataset results
    dataset_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(OUTPUT_DIR, dataset_name)
    os.makedirs(output_dir, exist_ok=True)

    # Analyze the dataset
    analysis = analyze_data(df)

    # Generate visualizations
    images = generate_visualizations(df, output_dir)

    # Ask LLM for insights
    narrative = ask_llm_for_insights(analysis)

    # Save README with narrative and images
    readme_path = save_readme(narrative, images, output_dir,analysis)

    print(f"Analysis complete for {file_path}. Results saved in {output_dir}.")
    return output_dir


def main():
    """Main function to handle command-line arguments and process datasets."""
    parser = argparse.ArgumentParser(description="Perform EDA on multiple datasets.")
    parser.add_argument("files", metavar="FILE", type=str, nargs="+",
                        help="Paths to the dataset files to analyze.")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []
    for file in args.files:
        if os.path.exists(file):
            result = process_dataset(file)
            if result:
                results.append(result)
        else:
            print(f"Error: File {file} does not exist.")

    if results:
        print("\nEDA completed. Results saved in:")
        for result in results:
            print(f" - {result}")
    else:
        print("\nNo valid datasets processed.")


if __name__ == "__main__":
    main()
