from playwright.async_api import async_playwright

async def convert_svg_to_png(svg_path, png_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # 读取 SVG 内容
        with open(str(svg_path), "r", encoding="utf-8") as f:
            svg_content = f.read()

        # 用 data URI 加载 SVG
        await page.set_content(f"""
        <html>
        <body style="margin:0">
        {svg_content}
        </body>
        </html>
        """)

        # 等待图片加载完成
        await page.wait_for_timeout(1000)

        # 先设置视口高度为你想要的长度
        await page.set_viewport_size({"width": 1200, "height": 1480})

        # 截图（不用 full_page，只截当前视口）
        await page.screenshot(
            path=png_path,
            full_page=False
        ) 
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(convert_svg_to_png("save.svg", "save.png"))