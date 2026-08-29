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

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Калькулятор проводок ГУ РК</title>
        <!-- Подключение библиотеки XLSX для экспорта таблицы в Excel -->
        <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; display: flex; flex-direction: column; min-height: 93vh; }}
            .content {{ flex: 1; }}
            label {{ font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }}
            select, input {{ width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
            .btn {{ padding: 12px 20px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; font-weight: bold; margin-top: 10px; }}
            .btn-calc {{ background-color: #27ae60; color: white; width: 100%; }}
            .btn-excel {{ background-color: #1e7e34; color: white; margin-top: 15px; display: none; }}
            .btn-kaspi {{ background-color: #f14635; color: white; width: 100%; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: #fff; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #eef4f0; }}
            #result {{ margin-top: 25px; padding: 15px; border-radius: 6px; background-color: #ffffff; border: 1px solid #e0e0e0; }}
            footer {{ margin-top: 40px; text-align: center; font-size: 12px; color: #777; padding: 15px 0 5px 0; border-top: 1px solid #e0e0e0; }}
            
            /* Modal Styles */
            .modal {{ display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }}
            .modal-content {{ background-color: #fff; margin: 5% auto; padding: 25px; border-radius: 12px; width: 90%; max-width: 400px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
            .close-btn {{ float: right; font-size: 22px; cursor: pointer; color: #aaa; font-weight: bold; }}
            .qr-container {{ background: #fff; padding: 15px; border: 2px dashed #f14635; border-radius: 8px; margin: 15px 0; display: inline-block; }}
            .qr-container img {{ width: 200px; height: 200px; display: block; margin: 0 auto; }}
        </style>
    </head>
    <body>
        <div class="content">
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

            <button type="button" class="btn btn-calc" onclick="calculate()">Сформировать проводки</button>

            <div id="result">Здесь появится результат расчета</div>
            <button id="excelBtn" class="btn btn-excel" onclick="exportToExcel()">📥 Скачать проводки в Excel (.xlsx)</button>
        </div>

        <!-- Модальное окно подписки Kaspi QR -->
        <div id="kaspiModal" class="modal">
            <div class="modal-content">
                <span class="close-btn" onclick="closeKaspiModal()">&times;</span>
                <h3 style="color: #f14635; margin-top:0;">Подписка на 1 месяц</h3>
                <p style="font-size: 18px; font-weight: bold; margin: 10px 0; color: #2c3e50;">Стоимость: 1$ (~500 ₸)</p>
                <p style="font-size: 14px; color: #666;">Отсканируйте QR-код через приложение Kaspi.kz для активации доступа на 30 дней:</p>
                
                <div class="qr-container">
                    <div id="qrImageArea"></div>
                </div>

                <button class="btn btn-kaspi" onclick="openKaspiPay()">Оплатить 500 ₸ через Kaspi Pay</button>
            </div>
        </div>

        <footer>
            Разработчик: А.Т.Н., 2026 год
        </footer>

        <script>
        let currentPayUrl = '';
        let currentEntriesData = [];

        function startDictation() {{
            const micBtn = document.getElementById('micBtn');
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (!SpeechRecognition) {{
                alert("Браузер не поддерживает голосовой ввод. Используйте Chrome или Edge.");
                return;
            }}

            const recognition = new SpeechRecognition();
            recognition.lang = 'ru-RU';
            micBtn.innerText = '🔴';

            recognition.onresult = function(event) {{
                let transcript = event.results[0][0].transcript;
                let numbersOnly = transcript.replace(/[^0-9]/g, '');
                if (numbersOnly) document.getElementById('amount').value = numbersOnly;
                micBtn.innerText = '🎤';
            }};

            recognition.onerror = function() {{ micBtn.innerText = '🎤'; }};
            recognition.onend = function() {{ micBtn.innerText = '🎤'; }};
            recognition.start();
        }}

        async function showKaspiQR() {{
            try {{
                const res = await fetch('/get_pay_qr/default_user');
                const data = await res.json();
                currentPayUrl = data.url || 'https://kaspi.kz';
                
                const qrImageArea = document.getElementById('qrImageArea');
                // Генерация QR-кода на основе ссылки Kaspi Pay
                const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${{encodeURIComponent(currentPayUrl)}}`;
                
                qrImageArea.innerHTML = `<img src="${{qrApiUrl}}" alt="Kaspi QR Code"><br><a href="${{currentPayUrl}}" target="_blank" style="color:#f14635; font-weight:bold; font-size:14px; display:inline-block; margin-top:8px;">Открыть прямую ссылку</a>`;
                
                document.getElementById('kaspiModal').style.display = 'block';
            }} catch (e) {{
                alert('Не удалось получить QR-код для оплаты.');
            }}
        }}

        function closeKaspiModal() {{
            document.getElementById('kaspiModal').style.display = 'none';
        }}

        function openKaspiPay() {{
            if (currentPayUrl) {{
                window.open(currentPayUrl, '_blank');
            }} else {{
                alert('Ссылка оплаты Kaspi временно недоступна');
            }}
        }}

        async function calculate() {{
            const code = document.getElementById('account_select').value;
            const amountInput = document.getElementById('amount').value;
            const amount = parseFloat(amountInput);
            const resultDiv = document.getElementById('result');
            const excelBtn = document.getElementById('excelBtn');

            excelBtn.style.display = 'none';
            currentEntriesData = [];

            if (!amount || amount <= 0) {{
                alert('Пожалуйста, введите корректную сумму');
                return;
            }}

            resultDiv.innerHTML = '<em>Идет расчет и обработка данных...</em>';

            try {{
                const response = await fetch('/process-account/', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ code: code, amount: amount, user_id: 'default_user' }})
                }});

                if (response.status === 402) {{
                    resultDiv.innerHTML = `<div style="color: #f14635; padding: 10px;"><strong>Необходима подписка!</strong> Стоимость доступа: 1$ (~500 ₸) в месяц.</div>`;
                    showKaspiQR();
                    return;
                }}

                if (!response.ok) {{
                    const err = await response.json();
                    resultDiv.innerHTML = `<div style="color: red;"><strong>Ошибка сервера:</strong> ${{err.detail || 'Не удалось выполнить расчет'}}</div>`;
                    return;
                }}

                const data = await response.json();
                
                let html = '<h3>Результат расчета:</h3>';
                const mainName = data.name || data.account_name || data.title || '';
                if (mainName) html += `<p><strong>Наименование:</strong> ${{mainName}}</p>`;

                const generalDesc = data.operation || data.description || data.op_name || '';

                if (data.entries && Array.isArray(data.entries) && data.entries.length > 0) {{
                    currentEntriesData = data.entries;
                    html += '<table id="entriesTable"><thead><tr><th>Дебет</th><th>Кредит</th><th>Сумма (₸)</th><th>Описание хозяйственной операции</th></tr></thead><tbody>';
                    data.entries.forEach(e => {{
                        let desc = e.description || e.desc || e.op || e.operation || e.title || e.comment || e.details || generalDesc || '-';
                        let dt = e.dt || e.debit || '-';
                        let kt = e.kt || e.credit || '-';
                        let entryAmount = e.amount || amount;
                        html += `<tr><td>${{dt}}</td><td>${{kt}}</td><td>${{entryAmount}}</td><td>${{desc}}</td></tr>`;
                    }});
                    html += '</tbody></table>';
                    excelBtn.style.display = 'inline-block';
                }} else {{
                    html += '<pre style="background:#f0f0f0; padding:10px; border-radius:6px; overflow-x:auto;">' + JSON.stringify(data, null, 2) + '</pre>';
                }}

                resultDiv.innerHTML = html;
            }} catch (err) {{
                resultDiv.innerHTML = `<div style="color: red;"><strong>Ошибка JS:</strong> ${{err.message}}</div>`;
            }}
        }}

        // Функция экспорта результатов в Excel (.xlsx)
        function exportToExcel() {{
            const table = document.getElementById('entriesTable');
            if (!table) {{
                alert('Нет данных для выгрузки в Excel');
                return;
            }}
            
            const wb = XLSX.utils.table_to_book(table, {{ sheet: "Бухгалтерские проводки" }});
            XLSX.writeFile(wb, "Проводки_ГУ_РК.xlsx");
        }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/process-account/")
def process_account(req: AccountProcessRequest):
    check_sub = getattr(BillingManager, "is_subscription_active", None)
    if callable(check_sub) and not check_sub(req.user_id):
        raise HTTPException(status_code=402, detail="Необходима подписка на 1 месяц (1$ / 500 ₸)")
    
    return AI_engine.process_account_code(req.code, req.amount)

@app.get("/get_pay_qr/{user_id}")
def get_pay_qr(user_id: str):
    create_link = getattr(BillingManager, "create_kaspi_payment_link", None)
    if callable(create_link):
        return create_link(user_id, amount=500)
    return {"url": "https://kaspi.kz"}

@app.post("/kaspi-webhook/")
def kaspi_webhook(user_id: str, status: str):
    webhook_fn = getattr(BillingManager, "process_kaspi_webhook", None)
    if callable(webhook_fn):
        success = webhook_fn(user_id, status)
        if success:
            return {"status": "ok", "message": "Subscription updated for 1 month"}
    raise HTTPException(status_code=400, detail="Payment processing failed")