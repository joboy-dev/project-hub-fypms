def count_lines_in_file(file_path: str) -> int:
    count = 0
    with open(file_path, "rb") as f:  # Open in binary mode for speed
        for _ in f:
            count += 1
    return count