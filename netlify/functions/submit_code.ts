import type { Handler } from '@netlify/functions';
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

interface Payload {
    jsessionid: string;
    username: string;
    problem_id: string;
    language: string;
    source: string;
}

export const handler: Handler = async (event, context) => {
    if (!event.body) return { statusCode: 400, body: 'Missing body' };
    const payload: Payload = JSON.parse(event.body);

    const headers = {
        'Cookie': `JSESSIONID=${payload.jsessionid}`,
        'User-Agent': 'Mozilla/5.0'
    };

    // 提交代码
    const submitUrl = 'https://codeforces.com/problemset/submit';
    const formData = new URLSearchParams();
    formData.append('csrf_token', ''); // 真实部署中要获取页面csrf_token
    formData.append('action', 'submitSolutionFormSubmitted');
    formData.append('submittedProblemCode', payload.problem_id);
    formData.append('programTypeId', payload.language);
    formData.append('source', payload.source);

    const submitResp = await fetch(submitUrl, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
        redirect: 'manual'
    });

    if (submitResp.status !== 302) {
        return { statusCode: 500, body: JSON.stringify({ error: '提交失败，可能缺少csrf_token或被Cloudflare阻止' }) };
    }

    // 返回成功提交信息
    return { statusCode: 200, body: JSON.stringify({ message: '提交成功！请在Codeforces查看结果' }) };
};
