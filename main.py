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
    # Генерируем полный список счетов для select
    options_html = "".join([
        f'<option value="{code}">{code} — {name}</option>'
        for code, name in ai_engine.chart_of_accounts.items()
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Калькулятор проводок ГУ РК (Подписка Kaspi QR)</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }}
            .container {{ max-width: 850px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); position: relative; }}
            h2 {{ color: #2c3e50; text-align: center; margin-bottom: 25px; border-bottom: 2px solid #27ae60; padding-bottom: 10px; margin-top: 10px; }}
            label {{ font-weight: bold; display: block; margin-top: 15px; }}
            select, input, button {{ width: 100%; padding: 12px; margin-top: 8px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box; font-size: 14px; }}
            .btn-calc {{ background-color: #27ae60; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 25px; font-size: 16px; transition: 0.2s; }}
            .btn-calc:hover {{ background-color: #219150; }}
            
            /* Панель подписки в правом верхнем углу */
            .top-bar {{ display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-bottom: 10px; }}
            .trial-badge {{ background: #e74c3c; color: white; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: bold; }}
            .kaspi-qr-btn {{ background-color: #f14635; color: white; border: none; padding: 7px 15px; border-radius: 20px; font-weight: bold; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px; width: auto; margin: 0; transition: 0.2s; }}
            .kaspi-qr-btn:hover {{ background-color: #d93828; box-shadow: 0 2px 8px rgba(241,70,53,0.4); }}

            /* Модальное окно оплаты */
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); }}
            .modal-content {{ background: white; margin: 8% auto; padding: 25px; border-radius: 12px; width: 360px; text-align: center; box-shadow: 0 5px 20px rgba(0,0,0,0.3); position: relative; }}
            .close-btn {{ position: absolute; right: 15px; top: 10px; font-size: 20px; cursor: pointer; color: #888; }}
            .close-btn:hover {{ color: #000; }}
            .kaspi-pay-confirm {{ background-color: #f14635; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 15px; font-size: 15px; padding: 12px; border-radius: 6px; width: 100%; }}
            .kaspi-pay-confirm:hover {{ background-color: #d93828; }}
            #qrcode {{ margin: 20px auto; display: flex; justify-content: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <span class="trial-badge" id="status-badge">1 месяц бесплатно</span>
                <button class="kaspi-qr-btn" onclick="openKaspiModal()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 3h8v8H3V3zm2 2v4h4V5H5zm8-2h8v8h-8V3zm2 2v4h4V5h-4zM3 13h8v8H3v-8zm2 2v4h4v-4H5zm13-2h3v2h-3v-2zm-5 0h3v3h-3v-3zm3 3h2v2h-2v-2zm-3 2h3v3h-3v-3zm5 0h3v3h-3v-3z"/></svg>
                    Оплатить Kaspi QR (2$)
                </button>
            </div>

            <h2>Веб-калькулятор проводок ГУ РК</h2>
            
            <label for="account_select">Выберите счет / субсчет из Плана счетов ГУ РК:</label>
            <select id="account_select">
                {options_html}
            </select>

            <label for="amount">Сумма операции (тенге ₸):</label>
            <div style="display: flex; gap: 8px;">
    <input type="number" id="amount" placeholder="Введите сумму" value="150000" style="flex-grow: 1;">
    <button type="button" id="micBtn" onclick="startDictation()" style="padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px;">🎤</button>
</div>

            <button class="btn-calc" onclick="calculate()">Сформировать проводки</button>

            <div id="result" style="display:none; margin-top: 25px;">
                <h3 id="res-desc" style="color:#2c3e50;"></h3>
                <table style="width:100%; border-collapse: collapse;" id="entries-table">
                    <thead>
                        <tr style="background:#eef4f0;">
                            <th style="border:1px solid #ddd; padding:8px;">Операция</th>
                            <th style="border:1px solid #ddd; padding:8px;">Дт</th>
                            <th style="border:1px solid #ddd; padding:8px;">Кт</th>
                            <th style="border:1px solid #ddd; padding:8px;">Спец.</th>
                            <th style="border:1px solid #ddd; padding:8px;">Сумма (₸)</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

        <!-- Модальное окно оплаты Kaspi QR -->
        <div id="kaspiModal" class="modal">
            <div class="modal-content">
                <span class="close-btn" onclick="closeKaspiModal()">&times;</span>
                <h3 style="color:#f14635; margin-top:0;">Оплата подписки Kaspi QR</h3>
                <p style="font-size:14px; color:#555;">Стоимость подписки: <b>1 000 ₸ / месяц</b> (2$)</p>
                <p style="font-size:13px; color:#777;">Отсканируйте QR-код в приложении <b>Kaspi.kz</b>:</p>
                <div id="qrcode"></div>
                <button class="kaspi-pay-confirm" onclick="checkPayment()">Подтвердить оплату</button>
            </div>
        </div>

        <script>
            const USER_ID = localStorage.getItem('gov_user_id') || 'usr_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('gov_user_id', USER_ID);

            async function openKaspiModal() {{
                const res = await fetch(`/get-pay-qr/${{USER_ID}}`);
                const payData = await res.json();
                
                document.getElementById('qrcode').innerHTML = "";
                new QRCode(document.getElementById("qrcode"), {{
                    text: payData.kaspi_url,
                    width: 180,
                    height: 180
                }});
                
                document.getElementById('kaspiModal').style.display = 'block';
            }}

            function closeKaspiModal() {{
                document.getElementById('kaspiModal').style.display = 'none';
            }}

            async function calculate() {{
                const code = document.getElementById('account_select').value;
                const amount = parseFloat(document.getElementById('amount').value);

                if (!amount || amount <= 0) return alert('Введите сумму');

                const response = await fetch('/process-account/', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ code, amount, user_id: USER_ID }})
                }});

                if (response.status === 402) {{
                    openKaspiModal();
                    return;
                }}

                if (response.ok) {{
                    const data = await response.json();
                    document.getElementById('res-desc').innerText = data.description;
                    const tbody = document.querySelector('#entries-table tbody');
                    tbody.innerHTML = '';
                    data.entries.forEach(e => {{
                        tbody.innerHTML += `<tr>
                            <td style="border:1px solid #ddd; padding:8px;">${{e.op}}</td>
                            <td style="border:1px solid #ddd; padding:8px; color:red;"><b>${{e.dt}}</b></td>
                            <td style="border:1px solid #ddd; padding:8px; color:green;"><b>${{e.kt}}</b></td>
                            <td style="border:1px solid #ddd; padding:8px;">${{e.spec}}</td>
                            <td style="border:1px solid #ddd; padding:8px;"><b>${{e.amount.toLocaleString('ru-RU')}} ₸</b></td>
                        </tr>`;
                    }});
                    document.getElementById('result').style.display = 'block';
                }}
            }}

            async function checkPayment() {{
                const res = await fetch(`/kaspi-webhook/?user_id=${{USER_ID}}&status=SUCCESS`, {{ method: 'POST' }});
                if (res.ok) {{
                    alert('Подписка успешно оплачена и продлена на 30 дней!');
                    closeKaspiModal();
                    document.getElementById('status-badge').innerText = 'Подписка активна';
                    document.getElementById('status-badge').style.background = '#27ae60';
                }}
            }}function startDictation() {
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
                let numbersOnly = transcript.replace(/\D/g, '');
                if (numbersOnly) document.getElementById('amount').value = numbersOnly;
                micBtn.innerText = '🎤';
            };

            recognition.onerror = function() { micBtn.innerText = '🎤'; };
            recognition.onend = function() { micBtn.innerText = '🎤'; };
            recognition.start();
        }
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