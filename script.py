import zipfile
import os
import sys
from PIL import Image
import shutil

def extract_zip(zip_file_path):
    """
    Extract zip file to a folder with the same name
    """
    output_dir = os.path.splitext(zip_file_path)[0]
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)
    return output_dir

def resize_images(directory, target_width=1280):
    """
    Resizes all images in the specified directory that have a width greater than the target width
    The images are resized to the target width while maintaining the original aspect ratio.
    """
    for filename in os.listdir(directory):
        if filename.endswith(".jpg") or filename.endswith(".png") or filename.endswith('.jpeg'):
            file_path = os.path.join(directory, filename)
            image = Image.open(file_path)
            width, height = image.size
            
            if width > target_width:
                new_width = target_width
                new_height = int(height * (new_width / width))
                resized_image = image.resize((new_width, new_height), resample=Image.LANCZOS)
                resized_image.save(file_path)
                # print(f"Resized {filename} to 1280 pixels wide.")
            else:
                print(f"Skipped {filename}")

def zip_folder(directory, suffix="-1280x"):
    """
    Creates a zip file containing all the files in the specified directory,
    with the name "{directory}{suffix}.zip". 
    The files will be extracted to the root folder when the zip file is extracted.
    """
    zip_filename = f"{directory}{suffix}.zip"
    # zip_filename = f"{directory}-1280x.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zip_file:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                print(file_path)
                zip_file.write(file_path, os.path.basename(file_path))
                print(os.path.basename(file_path))
                print(f"Added {file} to {zip_filename}.")
    
    print(f"Zip file '{zip_filename}' created successfully.")


def remove_folder(path):
    """
    Remove a folder and all its contents recursively.
    """
    try:
        shutil.rmtree(path)
        print(f"\n{path} was removed successfully.")
    except Exception as e:
        print(f"Error: Failed to remove folder '{path}' - {e}")

def find_files_with_extensions(folder_path, extensions):
    """
    Search for files with specified extensions in a folder and its subdirectories.
    
    Args:
        folder_path (str): Path to the folder to search in.
        extensions (list): List of file extensions (e.g., ['.zip', '.rar', '.cbz']).
        
    Returns:
        list: List of file paths that match the specified extensions.
    """
    matching_files = []
    for filename in os.listdir('.'):
        if any(filename.lower().endswith(ext.lower()) for ext in extensions):
            matching_files.append(filename)
    return matching_files

# folder_path = '.'
# extensions = ['.zip', '.rar', '.cbz']

# archives = find_files_with_extensions(folder_path, extensions)

def find_zip_files():
    return find_files_with_extensions('.', ['.zip', '.rar', '.cbz'])

def process_one_zip(zip_file_path):
    output_dir = extract_zip(zip_file_path)
    print(f"Zip file extracted to {output_dir}")
    resize_images(output_dir)
    zip_folder(output_dir)
    remove_folder(output_dir)


def main():
    if len(sys.argv) > 1:
        zip_file_path = sys.argv[1]
        process_one_zip(zip_file_path)
    else:
        print("Finding all zip/rar/cbz files in the current folder...")
        zip_files = find_zip_files()
        for zipfile in zip_files:
            process_one_zip(zipfile)



if __name__ == "__main__":
    main()