from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from accounting_ai import RKStateGovAccountingAI
from billing import BillingManager

app = FastAPI(title="Gov Accounting AI с Kaspi QR Подпиской")
ai_engine = RKStateGovAccountingAI()

class AccountProcessRequest(BaseModel):
    code: str
    amount: float
    user_id: str = "default_user"

@app.get("/", response_class=HTMLResponse)
def read_root():
    options_html = "".join([
        f'<option value="{code}">{code} - {name}</option>'
        for code, name in AI_engine.chart_of_accounts.items()
    ])

    js_code = """
    function startDictation() {
        const micBtn = document.getElementById('micBtn');
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            alert("Браузер не поддерживает голосовой ввод. Используйте Chrome или Edge.");
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'ru-RU';
        micBtn.innerText = '🔴';

        recognition.onresult = function(event) {
            let transcript = event.results[0][0].transcript;
            let numbersOnly = transcript.replace(/[^0-9]/g, '');
            if (numbersOnly) document.getElementById('amount').value = numbersOnly;
            micBtn.innerText = '🎤';
        };

        recognition.onerror = function() { micBtn.innerText = '🎤'; };
        recognition.onend = function() { micBtn.innerText = '🎤'; };
        recognition.start();
    }
    """

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Калькулятор проводок ГУ РК (Подписка Kaspi QR)</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }}
            label {{ font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }}
            select, input {{ width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
            .btn {{ padding: 12px 20px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; }}
            .btn-calc {{ background-color: #27ae60; color: white; margin-top: 20px; width: 100%; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #eef4f0; }}
        </style>
    </head>
    <body>
        <h2>Веб-калькулятор проводок ГУ РК</h2>
        
        <label for="account_select">Выберите счет / субсчет из Плана счетов ГУ РК:</label>
        <select id="account_select">
            {options_html}
        </select>

        <label for="amount">Сумма операции (тенге ₸):</label>
        <div style="display: flex; gap: 8px;">
            <input type="number" id="amount" placeholder="Введите сумму" style="flex-grow: 1;">
            <button type="button" id="micBtn" onclick="startDictation()" style="padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px;">🎤</button>
        </div>

        <button class="btn btn-calc" onclick="calculate()">Сформировать проводки</button>

        <script>
        {js_code}
        </script>
    </body>
    </html>
    """

@app.post("/process-account/")
def process_account(req: AccountProcessRequest):
    if not BillingManager.is_subscription_active(req.user_id):
        raise HTTPException(status_code=402, detail="Необходима подписка через Kaspi QR")
    return ai_engine.process_account_code(req.code, req.amount)

@app.get("/get-pay-qr/{user_id}")
def get_pay_qr(user_id: str):
    return BillingManager.create_kaspi_payment_link(user_id)

@app.post("/kaspi-webhook/")
def kaspi_webhook(user_id: str, status: str):
    success = BillingManager.process_kaspi_webhook(user_id, status)
    if success:
        return {"status": "ok", "message": "Subscription updated"}
    raise HTTPException(status_code=400, detail="Payment processing failed")