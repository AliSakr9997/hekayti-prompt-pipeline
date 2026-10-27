import json
import os
import dashscope
from dashscope import MultiModalConversation
import base64
from PIL import Image
import io
import requests
from pathlib import Path

dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def encode_base64_from_pil(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded_string}"

img_path = str(Path(__file__).resolve().parent / "test_fixture_child.jpg")
if not os.path.exists(img_path):
    print(f"Error: Could not find {img_path}")
    exit(1)

img = Image.open(img_path).convert('RGB')
image_data = encode_base64_from_pil(img)

messages = [
    {
        "role": "user",
        "content": [
            {"image": image_data},
            {"text": "A beautiful animated cartoon of a boy in a spaceship, vibrant colors, pixar style"}
        ]
    }
]

model = "qwen-image-2.0-pro-2026-06-22"

print(f"\n=============================================")
print(f"Testing model: {model}")
print(f"=============================================")
try:
    response = MultiModalConversation.call(
        model=model,
        messages=messages,
        stream=False,
        n=1,
        watermark=False,
        prompt_extend=True,
        size="1024*1024",
    )
    
    if response.status_code == 200:
        print(f"[{model}] SUCCESS!")
        for i, content in enumerate(response.output.choices[0].message.content):
            if "image" in content:
                img_url = content['image']
                print(f"[{model}] URL: {img_url}")
                # Download image
                img_resp = requests.get(img_url)
                if img_resp.status_code == 200:
                    filename = f"result_{model}.png"
                    with open(filename, 'wb') as f:
                        f.write(img_resp.content)
                    print(f"[{model}] Saved as {filename}")
            else:
                print(f"[{model}] Content: {content}")
    else:
        print(f"[{model}] HTTP status code: {response.status_code}")
        print(f"[{model}] Error code: {response.code}")
        print(f"[{model}] Error message: {response.message}")
except Exception as e:
    print(f"[{model}] Exception occurred: {str(e)}")
