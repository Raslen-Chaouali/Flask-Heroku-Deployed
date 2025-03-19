from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import yaml
import logging
import imaplib
import email
from email.header import decode_header
import re
import time
from datetime import datetime
import mysql.connector
import json
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "raslen",  # Replace with your root password
    "database": "antipiracy"
}

# Get today's date in the required format (e.g., "Feb 19, 2025")
today_date = datetime.today().strftime("%b %d, %Y")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Load credentials
def load_credentials(filepath):
    with open(filepath, 'r') as file:
        credentials = yaml.safe_load(file)
        return credentials['user'], credentials['password']

# Connect to Gmail IMAP
def connect_to_gmail_imap(user, password):
    imap_url = 'imap.gmail.com'
    mail = imaplib.IMAP4_SSL(imap_url)
    mail.login(user, password)
    mail.select("INBOX")
    return mail

# Extract OTP
def extract_otp_from_body(body):
    otp_pattern = r'Your password is:\s*(\d{6})'
    match = re.search(otp_pattern, body)
    return match.group(1) if match else None

# Get OTP from email
def get_last_received_email(mail, max_attempts=5, wait_time=5):
    for attempt in range(max_attempts):
        try:
            status, messages = mail.search(None, 'ALL')
            if status != "OK" or not messages[0]:
                time.sleep(wait_time)
                continue

            latest_email_id = messages[0].split()[-1]
            status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
            if status != "OK":
                time.sleep(wait_time)
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            otp = extract_otp_from_body(body)
            if otp:
                logging.info(f"Extracted OTP: {otp}")
                return otp

        except Exception as e:
            logging.error(f"Error while retrieving email: {e}")

        time.sleep(wait_time)

    logging.error("Failed to retrieve OTP after multiple attempts.")
    return None

@app.route('/trigger-selenium/<report_type>', methods=['GET'])
def trigger_selenium(report_type):
    url_id = request.args.get('urlId')
    if not url_id:
        return jsonify({"status": "error", "message": "URL ID is required"}), 400

    logging.info(f"Starting Selenium process for report type: {report_type} with URL ID: {url_id}")

    user, password = load_credentials("credentials.yaml")

    # Connect to MySQL
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Fetch data from the database
    cursor.execute("SELECT type, keyword, urls FROM urls WHERE id = %s", (url_id,))
    rows = cursor.fetchall()

    if not rows:
        return jsonify({"status": "error", "message": "No data found for the given URL ID"}), 404

    # Initialize Selenium WebDriver
    buster_extension_path = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data\Default\Extensions\mpbjkejclgfgadiemmefgebjfooflfhl\3.1.0_0"
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument(f"--load-extension={buster_extension_path}")
    #chrome_options.add_argument("--headless") 

# Start the browser with Buster extension
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Open the website
        driver.get("https://reportcontent.google.com/forms/dmca_search?product=websearch&uraw&hl=en&ctx=magi&sjid=11825459232159470708-EU&visit_id=638471220519775502-4048222145&rd=1")

        # Wait for email input field
        wait = WebDriverWait(driver, 20)
        email_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='email']")))

        # Enter email
        email_field.send_keys("mohamedraslencha@gmail.com")

        # Click "Verify" button
        verify_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//material-button[@data-test-id='email-submit-button']")))
        verify_button.click()

        logging.info("Email submitted. Waiting for OTP email...")

        # Wait for OTP email
        time.sleep(10)

        # Retrieve OTP
        mail = connect_to_gmail_imap(user, password)
        otp = get_last_received_email(mail)
        if not otp:
            logging.error("Failed to retrieve OTP.")
            return jsonify({"status": "error", "message": "Failed to retrieve OTP"}), 500

        # Enter OTP
        otp_field = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Input OTP']")))
        otp_field.send_keys(otp)

        # Click "Verify OTP" button
        verify_otp_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//material-button[contains(., 'Verify')]")))
        verify_otp_button.click()

        logging.info("OTP verification successful. Waiting for form page...")

        # Wait for the form page to load
        wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@aria-label="First name"]')))

        logging.info("Form loaded. Filling in the details...")

        # Fill the form
        if report_type == 'abderrahman':
            driver.find_element(By.XPATH, '//*[@aria-label="First name"]').send_keys("Abdelrahman")
        elif report_type == 'oussema':
            driver.find_element(By.XPATH, '//*[@aria-label="First name"]').send_keys("Osama")

        if report_type == 'abderrahman':
            driver.find_element(By.XPATH, '//*[@aria-label="Last name"]').send_keys("Ismail")
        elif report_type == 'oussema':
            driver.find_element(By.XPATH, '//*[@aria-label="Last name"]').send_keys("Khrisat")
        driver.find_element(By.XPATH, '//*[@aria-label="Company Name"]').send_keys("beIN Media group LLC")
        driver.find_element(By.XPATH, "//material-radio[contains(., 'Other')]").click()
        
        input_field = driver.find_element(By.XPATH, "//input[@aria-label='Add represented copyright holder']")
        input_field.clear()
        input_field.send_keys("beIN MENA WLL")
        
        driver.find_element(By.XPATH, '//*[@aria-label="Email address"]').send_keys("mohamedraslencha@gmail.com")
        
        dropdown_button = driver.find_element(By.CLASS_NAME, 'button')
        dropdown_button.click()

        # Step 2: Wait for the dropdown items to load (you may adjust the time)
        time.sleep(1)

        # Step 3: Locate the country "Egypt" in the dropdown list using the text and click it
        if report_type == 'abderrahman':
            egypt_option = driver.find_element(By.XPATH, "//span[contains(text(), 'Egypt')]")
            egypt_option.click()
        elif report_type == 'oussema':
            jordan_option = driver.find_element(By.XPATH, "//span[contains(text(), 'Jordan')]")
            jordan_option.click()
        
        driver.find_element(By.XPATH, "//material-radio[contains(., 'No')]").click()

        # Fill the "Identify and describe the copyrighted work" field based on the type
        description = ""
        example_urls = ""
        infringing_urls = []

        for row in rows:
            if row[0] == "https://www.tod.tv/ar/tvshows":
                description = f"TOD TV original series {row[1]}"
                example_urls = "https://www.tod.tv/ar/tvshows"
            elif row[0] == "https://www.beinsports.com/":
                description = "beIN live broadcasting for football matches"
                example_urls = "https://www.beinsports.com/"
            
            infringing_urls.append(row[2])  # Collect all URLs for the "Locations of infringing material" field

        # Fill the "Identify and describe the copyrighted work" field
        driver.find_element(By.XPATH, '//*[@aria-label="Enter your description here"]').send_keys(description)

        # Fill the "Where can we see an authorized example of work" field
        driver.find_element(By.XPATH, '//*[@aria-label="Enter your examples here"]').send_keys(example_urls)

        # Fill the "Locations of infringing material" field with all URLs (one per line)
        driver.find_element(By.XPATH, '//*[@aria-label="Enter your URL(s) here"]').send_keys("\n".join(infringing_urls))
        
        driver.find_element(By.XPATH, "//*[@aria-labelledby='mat-label-good-faith-belief']").click()
        driver.find_element(By.XPATH, "//*[@aria-labelledby='mat-label-accurate-information']").click()
        driver.find_element(By.XPATH, "//*[@aria-labelledby='mat-label-lumen-acknowledgement']").click()
        
        select_date_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Signed on this date of:*']")))
        select_date_button.click()
        time.sleep(2)
        date_input_field = wait.until(EC.element_to_be_clickable((By.XPATH, "(//input[@debugid='acx_177925851_179054344'])[2]")))
        date_input_field.send_keys(today_date)

        if report_type == 'abderrahman':
                driver.find_element(By.XPATH, '//*[@aria-label="Signature"]').send_keys("Abderahman Ismail")
        elif report_type == 'oussema':
            driver.find_element(By.XPATH, '//*[@aria-label="Signature"]').send_keys("Osama Khrisat ")
        WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[contains(@title, 'reCAPTCHA')]"))
        )

# Click the reCAPTCHA checkbox
        WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "recaptcha-checkbox"))
        ).click()
        driver.switch_to.default_content()

# Wait for the challenge iframe to appear and switch to it
        WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[contains(@title, 'recaptcha challenge')]"))
        )
        time.sleep(10)
# You may need to adjust this based on how long it takes to solve
        wrapper = driver.find_element(By.CSS_SELECTOR, ".button-holder.help-button-holder")
        wrapper.click()

# Use ActionChains to press TAB and click the solver button
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB).perform()  # Press Tab to shift focus to the button
        actions.send_keys(Keys.ENTER).perform() 
        driver.switch_to.default_content()
    # Wait for the button to be present in the DOM
        submit_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-test-id="submit-button"]'))
)

# Ensure the button is enabled (if needed)
        driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)

# Click the submit button
        submit_button.click()

        print("Submit button enabled and clicked successfully!")

        #submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='submit-button' and not(@disabled)]")))

# Click the Submit button
        #submit_button.click()
        report_id_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//p[@data-test-id='report-id']"))
    )

    # Extract the text (Report ID)
        report_id = report_id_element.text

    # Print the Report ID
        print("Report ID:", report_id)
        with open("report_id.json", "w") as file:
            json.dump({"url_id": url_id, "report_id": report_id}, file)
    

        

# Click the Submit button

        logging.info("Form filled successfully!")
        input("Press Enter to close the browser...")

    finally:
        driver.quit()

if __name__ == '__main__':
    app.run(port=5000, debug=True)
