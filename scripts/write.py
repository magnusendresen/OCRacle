def main(content, file):
    # Write content to file
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)