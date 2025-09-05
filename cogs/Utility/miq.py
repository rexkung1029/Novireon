from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
import io
import os
from PIL import Image, ImageDraw, ImageFont
import requests

INPUT_IMAGE_FILE = r"https://pbs.twimg.com/media/G0D2RkNaMAAh8zc?format=jpg&name=small"
CANVAS_WIDTH, CANVAS_HEIGHT = 1280, 720  # 圖片寬度, 高度
TEXT_COLOR = (255, 255, 255)  # 引言文字顏色
AUTHOR_COLOR = (200, 200, 200)  # 作者文字顏色
FOOTER_COLOR = (150, 150, 150)  # 底部標記顏色
#蒙板中心位置
VIGNETTE_MASK_CENTER_X = CANVAS_WIDTH*0
VIGNETTE_MASK_CENTER_Y = CANVAS_HEIGHT*0.5
VIGNETTE_MASK_RADIUS_PIXELS = 550 #蒙板大小
VIGNETTE_GRADIENT_START_RATIO = 0.7 #蒙板漸變起始處 (0 ~ 1)
#字型大小
QUOTE_FONT_SIZE = 48
AUTHOR_FONT_SIZE = 30
HANDLE_FONT_SIZE = 24
FOOTER_FONT_SIZE = 18
#字型路徑
FONT_PATH = r"data\GenSenRounded2-M.ttc"

def create_black_mask(
    width: int, 
    height: int, 
    center: tuple, 
    max_radius: int, 
    gradient_start_ratio: float
):
    """
    Args:
        width (int): 蒙版寬度。
        height (int): 蒙版高度。
        center (tuple): 蒙版中心 (x, y)。
        max_radius (int): 蒙版最大半徑 (漸變結束點)。
        gradient_start_ratio (float): 漸變起始位置的半徑比例 (0.0 到 1.0)。
    """
    center_x, center_y = center
    gradient_start_radius = int(max_radius * gradient_start_ratio)
    gradient_width = max_radius - gradient_start_radius

    alpha_mask = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(alpha_mask)

    if gradient_width > 0:
        for i in range(max_radius, gradient_start_radius, -1):
            progress_in_gradient = (i - gradient_start_radius) / gradient_width
            alpha = 255 * progress_in_gradient**1
            alpha = int(max(0, min(255, alpha)))
            
            x0, y0 = center_x - i, center_y - i
            x1, y1 = center_x + i, center_y + i
            draw.ellipse([x0, y0, x1, y1], fill=alpha)

    if gradient_start_radius > 0:
        x0_clear = center_x - gradient_start_radius
        y0_clear = center_y - gradient_start_radius
        x1_clear = center_x + gradient_start_radius
        y1_clear = center_y + gradient_start_radius
        draw.ellipse([x0_clear, y0_clear, x1_clear, y1_clear], fill=0)

    base_image = Image.new('RGB', (width, height), (0, 0, 0))
    base_image.putalpha(alpha_mask)
    
    return base_image

def image_handler(input_path: str):
    """
    從本地路徑或 URL 安全地開啟圖片。

    Args:
        input_path (str): 圖片的本地檔案路徑或線上 URL。

    Returns:
        Image.Image: 成功時回傳 Pillow Image 物件 (已轉換為 'RGBA')。
        None: 發生任何錯誤時回傳 None。
    """
    try:
        if input_path.startswith(('http://', 'https://')):
            print(f"正在從 URL 下載圖片: {input_path}")
            response = requests.get(input_path, stream=True)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
            image = Image.open(image_data).convert('RGBA')
            return image
        else:
            print(f"正在讀取本地圖片: {input_path}")
            image = Image.open(input_path).convert('RGBA')
            return image

    except FileNotFoundError:
        print(f"錯誤：找不到指定的本地圖片 '{input_path}'。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"錯誤：下載圖片時發生網路錯誤: {e}")
        return None
    except Exception as e:
        print(f"讀取或處理圖片 '{input_path}' 時發生錯誤: {e}")
        return None

def create_composite_image(
    input_path: str, 
    canvas_size: tuple,
    vignette_mask_info: dict
):
    """
    將輸入圖片放置在畫布上，並應用一個可自訂的暈影效果。
    """
    try:
        user_image = image_handler(input_path)
    except FileNotFoundError:
        print(f"錯誤：找不到指定的輸入圖片 '{input_path}'。")
        return
    except Exception as e:
        print(f"讀取圖片時發生錯誤: {e}")
        return

    canvas_width, canvas_height = canvas_size

    # 1. 創建一個黑色的 RGBA 畫布作為底層
    background_canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 255))

    # 2. 中心裁切圖片至正方形
    orig_w, orig_h = user_image.size
    crop_size = min(orig_w, orig_h)
    left = (orig_w - crop_size) // 2
    top = (orig_h - crop_size) // 2
    right = (orig_w + crop_size) // 2
    bottom = (orig_h + crop_size) // 2
    user_image = user_image.crop((left, top, right, bottom))

    # 3. 按比例縮放用戶圖片
    max_w = int(canvas_width * 0.4)
    max_h = int(canvas_height * 0.8)
    max_size = min(max_w, max_h)
    user_image = user_image.resize((max_size, max_size), Image.Resampling.LANCZOS)
    img_w, img_h = user_image.size

    # 3. 計算位置
    paste_center_x, paste_center_y = (canvas_width // 4, canvas_height // 2)
    paste_x = paste_center_x - (img_w // 2)
    paste_y = paste_center_y - (img_h // 2)


    # 4. 將用戶圖片貼上到畫布
    background_canvas.paste(user_image, (int(paste_x), int(paste_y)), user_image)

    # 5. 從字典中提取蒙版信息並生成蒙版
    mask_center = vignette_mask_info['center']
    mask_radius = vignette_mask_info['radius']
    mask_start_ratio = vignette_mask_info['start_ratio']
    
    print(f"正在生成中心點在 {mask_center}，半徑為 {mask_radius}px 的蒙版...")
    print(f"漸變效果將在半徑的 {mask_start_ratio*100:.0f}% 處開始。")
    vignette_mask = create_black_mask(
        width=canvas_width, 
        height=canvas_height, 
        center=mask_center,
        max_radius=mask_radius,
        gradient_start_ratio=mask_start_ratio
    )

    # 6. 疊加蒙版
    print("正在疊加蒙版...")
    final_image = Image.alpha_composite(background_canvas, vignette_mask)

    # 7. 保存結果
    return final_image

def create_quote_image(
    quote_text: str,
    author_info: str = None,
    custom_image_path: str = None,
    footer_text: str ="Creat by Noviren v0.1",
    output_path: str = None,
):
    mask_settings = {
        'center': (VIGNETTE_MASK_CENTER_X, VIGNETTE_MASK_CENTER_Y),
        'radius': VIGNETTE_MASK_RADIUS_PIXELS,
        'start_ratio': VIGNETTE_GRADIENT_START_RATIO
    }
    base_img = create_composite_image(
        input_path=custom_image_path,
        canvas_size=(CANVAS_WIDTH, CANVAS_HEIGHT),
        vignette_mask_info=mask_settings
    )
    draw = ImageDraw.Draw(base_img)
    quote_font = ImageFont.truetype(FONT_PATH, QUOTE_FONT_SIZE)
    author_font = ImageFont.truetype(FONT_PATH, AUTHOR_FONT_SIZE)
    handle_font = ImageFont.truetype(FONT_PATH, HANDLE_FONT_SIZE)
    footer_font = ImageFont.truetype(FONT_PATH, FOOTER_FONT_SIZE)

    text_area_left = CANVAS_WIDTH // 2 + 50
    text_area_right = CANVAS_WIDTH - 50
    text_area_width = text_area_right - text_area_left
    
    def wrap_text(text, font, max_width, draw_obj):
        """
        專為無空格語言（如中文）設計的逐字換行函式。
        """
        lines = []
        if not text:
            return lines

        current_line = ""
        for char in text:
            test_line = current_line + char
            if draw_obj.textlength(test_line, font=font) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        lines.append(current_line)
        return lines
    
    wrapped_quote_lines = wrap_text(quote_text, quote_font, text_area_width, draw)
    wrapped_quote_str = "\n".join(wrapped_quote_lines)

    quote_bbox = draw.multiline_textbbox((0, 0), wrapped_quote_str, font=quote_font, spacing=10)
    quote_height = quote_bbox[3] - quote_bbox[1]

    total_text_height = quote_height

    author_name = ""
    author_handle = ""
    if author_info:
        parts = author_info.split('\n', 1)
        author_name = parts[0].strip()
        if len(parts) > 1:
            author_handle = parts[1].strip()

        author_name_bbox = draw.textbbox((0, 0), f"- {author_name}", font=author_font)
        author_name_height = author_name_bbox[3] - author_name_bbox[1]
        total_text_height += author_name_height + 20

        if author_handle:
            handle_bbox = draw.textbbox((0, 0), author_handle, font=handle_font)
            handle_height = handle_bbox[3] - handle_bbox[1]
            total_text_height += handle_height + 5

    start_y = (CANVAS_HEIGHT - total_text_height) // 2

    draw.multiline_text((text_area_left, start_y), wrapped_quote_str, font=quote_font, fill=TEXT_COLOR, spacing=10)

    current_y = start_y + quote_height + 20
    if author_name:
        draw.text((text_area_left, current_y), f"- {author_name}", font=author_font, fill=AUTHOR_COLOR)
        current_y += (draw.textbbox((0,0), f"- {author_name}", font=author_font)[3] - draw.textbbox((0,0), f"- {author_name}", font=author_font)[1]) + 5
        
        if author_handle:
            draw.text((text_area_left + 15, current_y), author_handle, font=handle_font, fill=AUTHOR_COLOR)

    if footer_text:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        right_margin = 30
        bottom_margin = 30
        line_spacing = 5

        date_bbox = draw.textbbox((0, 0), date_str, font=footer_font)
        date_width = date_bbox[2] - date_bbox[0]
        date_height = date_bbox[3] - date_bbox[1]
        
        date_x = CANVAS_WIDTH - date_width - right_margin
        date_y = CANVAS_HEIGHT - date_height - bottom_margin
        draw.text((date_x, date_y), date_str, font=footer_font, fill=FOOTER_COLOR)

        footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_height = footer_bbox[3] - footer_bbox[1]
        
        footer_x = CANVAS_WIDTH - footer_width - right_margin
        footer_y = date_y - footer_height - line_spacing
        draw.text((footer_x, footer_y), footer_text, font=footer_font, fill=FOOTER_COLOR)

        if output_path is None:
            return base_img
        else:
            base_img.save(output_path)
            return output_path 

class MIQ:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="make_it_a_quote", description="製作經典語錄")
    @app_commands.describe(
        quote_context="引言的內容",
        author="引言的作者",
        custom_image="上傳自訂背景圖 (可選)"
    )
    async def make_it_a_quote(
        self,
        itat: discord.Interaction,
        quote_context: str,
        author: discord.Member,
        custom_image: discord.Attachment = None
    ):
        await itat.response.defer(thinking=True)

        image_url = ""
        if custom_image:
            if custom_image.content_type and "image" in custom_image.content_type:
                image_url = custom_image.url
            else:
                await itat.followup.send("請上傳有效的圖片檔案 (例如 .png, .jpg)。", ephemeral=True)
                return
        else:
            image_url = author.avatar.url
            output_filename = f"quote_{itat.id}.png"

        try:
            generated_path = create_quote_image(
                quote_text=quote_context,
                author_info=f"{author.display_name}\n{author.global_name}",
                custom_image_path=image_url,
                footer_text=f"Generated by Norvireon",
                output_path = output_filename,
            )

            if generated_path:
                await itat.followup.send(file=discord.File(generated_path))
            else:
                await itat.followup.send("圖片生成失敗，請檢查後台日誌或圖片連結是否有效。", ephemeral=True)

        except Exception as e:
            print(f"執行 /quote 指令時發生未預期錯誤: {e}")
            await itat.followup.send("執行指令時發生內部錯誤", ephemeral=True)
        finally:
            if os.path.exists(output_filename):
                os.remove(output_filename)

# --- 主程式執行區 ---
if __name__ == "__main__":
    img = create_quote_image(
        quote_text="有一個角色的技能叫做：你全家都伊利雅 我是說你是伊利雅就是伊利雅。",
        author_info="破大防人\nryanlion2062",
        custom_image_path=r"https://cdn.discordapp.com/avatars/857881096821145610/b7d8bb8db6f4b1a83c66ee13422957f9.png?size=1024",
        footer_text=f"Generated by Norvireon"
    )
    img.show()