import type { Handler } from '@netlify/functions';
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

export const handler: Handler = async (event, context) => {
    try {
        if (event.httpMethod !== 'POST') {
            return { statusCode: 405, body: JSON.stringify({ error: '只允许 POST' }) };
        }

        const body = JSON.parse(event.body || '{}');
        const { JSESSIONID, cookie39ce7, username, problemId, programTypeId, source } = body;

        if (!JSESSIONID || !cookie39ce7 || !username || !problemId || !programTypeId || !source) {
            return { statusCode: 400, body: JSON.stringify({ error: '缺少必要字段' }) };
        }

        // 1. 提交代码
        const submitResp = await fetch('https://codeforces.com/problemset/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cookie': `JSESSIONID=${JSESSIONID}; 39ce7=${cookie39ce7}`,
                'User-Agent': 'Mozilla/5.0'
            },
            body: new URLSearchParams({
                'action': 'submitSolutionFormSubmitted',
                'submittedProblemCode': problemId,
                'programTypeId': programTypeId,
                'source': source,
                'csrf_token': cookie39ce7
            })
        });

        if (!submitResp.ok) {
            return { statusCode: 500, body: JSON.stringify({ error: `提交失败，状态码 ${submitResp.status}` }) };
        }

        // 2. 轮询状态页
        const statusUrl = `https://codeforces.com/submissions/${username}`;
        let verdict = 'Pending';
        let time = '';
        let memory = '';
        const maxWait = 60; // 秒
        let waited = 0;

        while (waited < maxWait) {
            const statusResp = await fetch(statusUrl, {
                headers: {
                    'Cookie': `JSESSIONID=${JSESSIONID}; 39ce7=${cookie39ce7}`,
                    'User-Agent': 'Mozilla/5.0'
                }
            });

            const html = await statusResp.text();
            const $ = cheerio.load(html);

            // 找到第一条对应题目的提交记录
            let found = false;
            $('table.status-frame-datatable tr').each((i, el) => {
                if (i === 0) return; // 表头
                const cols = $(el).find('td');
                const colProblem = $(cols[3]).text().trim();
                const colVerdict = $(cols[5]).text().trim();
                const colTime = $(cols[7]).text().trim();
                const colMemory = $(cols[6]).text().trim();

                if (colProblem === problemId) {
                    verdict = colVerdict;
                    time = colTime;
                    memory = colMemory;
                    found = true;
                    return false; // break
                }
            });

            if (verdict !== 'Pending') break;
            await new Promise(r => setTimeout(r, 2000));
            waited += 2;
        }

        return { statusCode: 200, body: JSON.stringify({ verdict, time, memory }) };
    } catch (err: any) {
        return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
    }
};
