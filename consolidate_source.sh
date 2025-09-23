#!/bin/bash

# Script to consolidate all Python source files into a single text file
# Usage: ./consolidate_source.sh

OUTPUT_FILE="slideshow.txt"
PROJECT_ROOT="/Users/markpinnuck/Dev/GitHub/SlideShowBuilder"

# Change to project directory
cd "$PROJECT_ROOT"

# Clear the output file
> "$OUTPUT_FILE"

echo "=== SlideShow Builder - Source Code Consolidation ===" >> "$OUTPUT_FILE"
echo "Generated on: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Generate and add project tree
echo "=== PROJECT STRUCTURE ===" >> "$OUTPUT_FILE"
tree -I '__pycache__|*.pyc|.venv|.DS_Store' >> "$OUTPUT_FILE" 2>/dev/null || {
    echo "Note: 'tree' command not found, using 'find' instead" >> "$OUTPUT_FILE"
    find . -type f -name "*.py" | grep -v __pycache__ | sort >> "$OUTPUT_FILE"
}
echo "" >> "$OUTPUT_FILE"
echo "=================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Find all Python files (excluding __pycache__ and .venv)
find . -name "*.py" -not -path "./__pycache__/*" -not -path "./.venv/*" | sort | while read -r file; do
    # Get relative path (remove leading ./)
    relative_path="${file#./}"
    
    echo "=== FILE: $relative_path ===" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Add file contents
    cat "$file" >> "$OUTPUT_FILE"
    
    echo "" >> "$OUTPUT_FILE"
    echo "=== END OF $relative_path ===" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

echo "Source consolidation complete! Output saved to: $OUTPUT_FILE"
echo "Files included:"
find . -name "*.py" -not -path "./__pycache__/*" -not -path "./.venv/*" | sort