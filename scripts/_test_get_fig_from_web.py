from utils import select_image_from_query

def test_select_image_from_query():
    query = "Moody diagram"
    image_url = select_image_from_query(query)
    print(f"Image URL for query '{query}': {image_url}")
    assert image_url is not None, "No image URL returned"
    assert image_url.startswith("http"), "Returned URL is not valid"

if __name__ == "__main__":
    test_select_image_from_query()
    print("Test passed.")