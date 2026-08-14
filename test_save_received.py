from pipeline_utils import save_received_capture

fake_json = '{"tile_id": 2, "strokes": []}'
path = save_received_capture(fake_json)
print("Saved to:", path)
