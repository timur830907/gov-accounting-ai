from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import accounting_ai
import billing

app = FastAPI(title="Gov Accounting AI")

# Инициализируем класс счетов
AI_engine = accounting_ai.RKStateGovAccountingAI()

# Инициализируем менеджер биллинга
BillingManager = billing.BillingManager() if hasattr(billing, "BillingManager") else billing

class AccountProcessRequest(BaseModel):
    code: str
    amount: float
    user_id: str = "default_user"

@app.get("/", response_class=HTMLResponse)
def read_root():
    chart = getattr(AI_engine, "chart_of_accounts", {})
    
    options_html = "".join([
        f'<option value="{code}">{code} - {name}</option>'
        for code, name in chart.items()
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

    async function calculate() {
        const code = document.getElementById('account_select').value;
        const amount = parseFloat(document.getElementById('amount').value);
        const resultDiv = document.getElementById('result');

        if (!amount || amount <= 0) {
            alert('Пожалуйста, введите корректную сумму');
            return;
        }

        resultDiv.innerHTML = '<p>Загрузка и расчет проводок...</p>';

        try {
            const response = await fetch('/process-account/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code, amount: amount, user_id: 'default_user' })
            });

            if (!response.ok) {
                const err = await response.json();
                resultDiv.innerHTML = `<div style="color: red; margin-top: 15px;">Ошибка: ${err.detail || 'Не удалось выполнить расчет'}</div>`;
                return;
            }

            const data = await response.json();
            
            let html = '<h3 style="margin-top:20px;">Результат расчета:</h3>';
            html += `<p><strong>Наименование:</strong> ${data.name || ''}</p>`;

            if (data.entries && data.entries.length > 0) {
                html += '<table><thead><tr><th>Дебет</th><th>Кредит</th><th>Сумма (₸)</th><th>Описание</th></tr></thead><tbody>';
                data.entries.forEach(e => {
                    html += `<tr><td>${e.dt || ''}</td><td>${e.kt || ''}</td><td>${e.amount || ''}</td><td>${e.description || ''}</td></tr>`;
                });
                html += '</tbody></table>';
            } else {
                html += '<pre style="background:#eef; padding:10px; border-radius:6px;">' + JSON.stringify(data, null, 2) + '</pre>';
            }

            resultDiv.innerHTML = html;
        } catch (err) {
            resultDiv.innerHTML = '<div style="color: red; margin-top: 15px;">Ошибка соединения с сервером.</div>';
        }
    }
    """

    html_template = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Калькулятор проводок ГУ РК</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }
            label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
            select, input { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
            .btn { padding: 12px 20px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; }
            .btn-calc { background-color: #27ae60; color: white; margin-top: 20px; width: 100%; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #eef4f0; }
        </style>
    </head>
    <body>
        <h2>Веб-калькулятор проводок ГУ РК</h2>
        
        <label for="account_select">Выберите счет / субсчет из Плана счетов ГУ РК:</label>
        <select id="account_select">
            __OPTIONS__
        </select>

        <label for="amount">Сумма операции (тенге ₸):</label>
        <div style="display: flex; gap: 8px;">
            <input type="number" id="amount" placeholder="Введите сумму" style="flex-grow: 1;">
            <button type="button" id="micBtn" onclick="startDictation()" style="padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px;">🎤</button>
        </div>

        <button class="btn btn-calc" onclick="calculate()">Сформировать проводки</button>

        <div id="result"></div>

        <script>
        __JS_CODE__
        </script>
    </body>
    </html>
    """

    final_html = html_template.replace("__OPTIONS__", options_html).replace("__JS_CODE__", js_code)
    return HTMLResponse(content=final_html)

@app.post("/process-account/")
def process_account(req: AccountProcessRequest):
    check_sub = getattr(BillingManager, "is_subscription_active", None)
    if callable(check_sub) and not check_sub(req.user_id):
        raise HTTPException(status_code=402, detail="Необходима подписка через Kaspi QR")
    
    return AI_engine.process_account_code(req.code, req.amount)

@app.get("/get_pay_qr/{user_id}")
def get_pay_qr(user_id: str):
    create_link = getattr(BillingManager, "create_kaspi_payment_link", None)
    if callable(create_link):
        return create_link(user_id)
    return {"url": ""}

@app.post("/kaspi-webhook/")
def kaspi_webhook(user_id: str, status: str):
    webhook_fn = getattr(BillingManager, "process_kaspi_webhook", None)
    if callable(webhook_fn):
        success = webhook_fn(user_id, status)
        if success:
            return {"status": "ok", "message": "Subscription updated"}
    raise HTTPException(status_code=400, detail="Payment processing failed")