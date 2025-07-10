from project_config import *
import shutil

def purge_images():
    """
    Purge all folders in the 'images' directory.
    """
    if not IMG_DIR.exists():
        print(f"❌ Directory '{IMG_DIR}' does not exist.")
        return

    for item in IMG_DIR.glob('*'):
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"✅ Deleted folder: {item.name}")
            else:
                print(f"❌ Skipped (not a folder): {item.name}")
        except Exception as e:
            print(f"❌ Error deleting {item.name}: {e}")

    print("✅ All folders have been purged.")

purge_images()