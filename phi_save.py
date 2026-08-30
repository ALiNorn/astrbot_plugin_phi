import http.client
import json

def save_svg(session_token, output_path, openapi_token):
    conn = http.client.HTTPSConnection("r0semi.xtower.site")
    payload = json.dumps({
        "sessionToken": session_token,
        "taptapVersion":"cn",
        "n": 27,
        "theme": "black"
    })
    headers = {
        'X-OpenApi-Token': openapi_token,
        'Content-Type': 'application/json'
    }

    try:
        conn.request("POST", "/api/v1/open/image/bn?format=svg", payload, headers)
        res = conn.getresponse()
        data = res.read()
        
        # 保存为 SVG 文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(data.decode("utf-8"))
        print(f"SVG 文件已保存为 {output_path}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 示例调用
    session_token = "81aes0oxqg2zeespzpydfhago"
    openapi_token = "pgr_live_RKMBVpKlPqCTS4CR2p0BS2sGk857pzst"
    save_svg(session_token, "save.svg", openapi_token)