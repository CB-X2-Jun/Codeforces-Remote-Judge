import json
import requests
from bs4 import BeautifulSoup
import time
from jinja2 import Template
from urllib.parse import parse_qs

CODEFORCES_BASE = "https://codeforces.com"

INDEX_HTML = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Codeforces 远程评测</title>
<style>
body{font-family: Arial; max-width:900px;margin:40px auto;padding:0 20px;}
label,input,select,textarea,button{display:block;margin-bottom:10px;width:100%;}
textarea{height:300px;font-family: monospace;}
button{padding:8px; background:#4CAF50; color:white; border:none; cursor:pointer;}
button:hover{background:#45a049;}
.result{padding:10px;border-radius:5px; margin:5px 0; font-weight:bold;}
.ac{background:#d4edda;color:#155724;border:1px solid #c3e6cb;}
.wa{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
.ce{background:#fff3cd;color:#856404;border:1px solid #ffeeba;}
.tle{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
.re{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
</style>
</head>
<body>
<h2>Codeforces 远程评测</h2>
<form method="post">
<label>JSESSIONID: <input name="jsessionid" type="text" required></label>
<label>用户名: <input name="username" type="text" required></label>
<label>题号: <input name="problem_id" type="text" required></label>
<label>语言:
<select name="language">
<option value="42">GNU C++17</option>
<option value="43">GNU C++20</option>
<option value="50">Python 3</option>
</select></label>
<label>源代码:<br><textarea name="source" required></textarea></label>
<button type="submit">提交</button>
</form>
</body>
</html>
'''

RESULT_HTML = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>提交结果</title>
<style>
body{font-family: Arial; max-width:900px;margin:40px auto;padding:0 20px;}
.result{padding:10px;border-radius:5px; margin:5px 0; font-weight:bold;}
.ac{background:#d4edda;color:#155724;border:1px solid #c3e6cb;}
.wa{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
.ce{background:#fff3cd;color:#856404;border:1px solid #ffeeba;}
.tle{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
.re{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
</style>
</head>
<body>
<h2>提交结果</h2>
<div><strong>题目:</strong> {{problem}}</div>
<div><strong>提交ID:</strong> {{runid}}</div>
<div class="result {{verdict|lower}}">判定结果: {{verdict}}</div>
<div><strong>用时:</strong> {{time}}</div>
<div><strong>内存:</strong> {{memory}}</div>
{% if compile_info %}
<h3>编译信息</h3>
<pre>{{compile_info}}</pre>
{% endif %}
<p><a href="/">返回首页</a></p>
</body>
</html>
'''

def handler(event, context):
    if event['httpMethod'] == 'GET':
        return {"statusCode":200, "headers":{"Content-Type":"text/html"}, "body":INDEX_HTML}

    body = event['body']
    if event.get('isBase64Encoded'):
        import base64
        body = base64.b64decode(body).decode('utf-8')
    form = parse_qs(body)
    jsessionid = form.get('jsessionid',[''])[0]
    username = form.get('username',[''])[0]
    problem_id = form.get('problem_id',[''])[0]
    language = form.get('language',[''])[0]
    source = form.get('source',[''])[0]

    session = requests.Session()
    session.cookies.set('JSESSIONID', jsessionid, domain='codeforces.com')
    headers = {'User-Agent':'Mozilla/5.0'}

    # 获取 CSRF Token
    try:
        r = session.get(f"{CODEFORCES_BASE}/problemset/submit", headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf_token = soup.find('input', {'name':'csrf_token'})['value']
    except:
        csrf_token = None

    if not csrf_token:
        return {"statusCode":200,"body":"无法获取 CSRF Token，请检查 JSESSIONID"}

    # 提交代码
    submit_url = f"{CODEFORCES_BASE}/problemset/submit"
    data = {
        "csrf_token": csrf_token,
        "action":"submitSolutionFormSubmitted",
        "submittedProblemCode": problem_id,
        "programTypeId": language,
        "source": source,
    }
    session.post(submit_url, data=data, headers=headers)

    # 轮询获取状态
    runid = ""
    verdict = ""
    time_used = ""
    memory_used = ""
    max_wait = 60
    interval = 2
    waited = 0

    status_url = f"{CODEFORCES_BASE}/submissions/{username}"
    while waited < max_wait:
        r = session.get(status_url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', {'class':'status-frame-datatable'})
        if table:
            row = table.find('tr')
            if row:
                cols = row.find_all('td')
                if len(cols)>=6:
                    runid = cols[0].text.strip()
                    verdict = cols[3].text.strip()
                    time_used = cols[4].text.strip()
                    memory_used = cols[5].text.strip()
                    if verdict != "In queue" and verdict != "Running":
                        break
        time.sleep(interval)
        waited += interval

    compile_info = ""
    if "Compilation" in verdict:
        # 获取编译信息
        try:
            r = session.get(f"{CODEFORCES_BASE}/data/submitSource.json?submissionId={runid}", headers=headers)
            compile_info = r.json().get('compileInfo', '')
        except:
            compile_info = ""

    html_body = Template(RESULT_HTML).render(
        problem=problem_id,
        runid=runid,
        verdict=verdict,
        time=time_used,
        memory=memory_used,
        compile_info=compile_info
    )
    return {"statusCode":200, "headers":{"Content-Type":"text/html"}, "body":html_body}
