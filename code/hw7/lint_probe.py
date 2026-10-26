import os


def current_folder() -> str:
    folder_name = os.path.basename(os.getcwd())
    return folder_name
