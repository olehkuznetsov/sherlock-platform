import json

def count_function_entrances(filename):
    """Counts the number of entrances for each function name in a JSON file.

    Args:
        filename: The path to the JSON file.

    Returns:
        A dictionary where keys are function names and values are their counts.
        Returns an empty dictionary if the file is not found or an error occurs.
    """

    function_counts = {}

    try:
        with open(filename, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "function" in data and "name" in data["function"]:
                        function_name = data["function"]["name"]
                        function_counts[function_name] = function_counts.get(function_name, 0) + 1
                except json.JSONDecodeError:
                    # Handle cases where a line is not valid JSON
                    #print(f"Skipping invalid JSON line: {line.strip()}")  # Optional: print the skipped line
                    pass  # Or continue to the next line
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return {}
    except Exception as e: # Catch any other exceptions
        print(f"An error occurred: {e}")
        return {}

    return function_counts


if __name__ == "__main__":
    filename = "tests/Pixel 9 Pro/frames/asphalt9_00750.jsonl"  # Replace with your file name
    counts = count_function_entrances(filename)

    if counts:
        for function_name, count in counts.items():
            print(f"{function_name} {count}")