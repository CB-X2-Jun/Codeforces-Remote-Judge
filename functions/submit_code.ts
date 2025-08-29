import type { Handler } from "@netlify/functions";
import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";

function parseCookieString(cookieStr: string): { name: string; value: string }[] {
  // 支持直接粘贴 "JSESSIONID=...; 39ce7=..." 这种格式
  return cookieStr
    .split(";")
    .map(s => s.trim())
    .filter(Boolean)
    .map(pair => {
      const eq = pair.indexOf("=");
      if (eq === -1) return null;
      const name = pair.slice(0, eq).trim();
      const value = pair.slice(eq + 1).trim();
      return { name, value };
    })
    .filter((x): x is { name: string; value: string } => !!x);
}

async function setCookies(page: puppeteer.Page, cookieStr: string) {
  const cookies = parseCookieString(cookieStr);
  if (cookies.length === 0) throw new Error("Cookie 为空或格式错误");
  // 先打开 codeforces，确保 domain 可被设置
  await page.goto("https://codeforces.com/enter", { waitUntil: "domcontentloaded" });
  await page.setCookie(
    ...cookies.map(c => ({
      name: c.name,
      value: c.value,
      domain: ".codeforces.com",
      path: "/",
      httpOnly: false,
      secure: true
    }))
  );
}

async function submitSolution(page: puppeteer.Page, contestId: string, problemIndex: string, languageId: string, sourceCode: string) {
  // 使用 contest 提交页（更稳定）
  const submitUrl = `https://codeforces.com/contest/${contestId}/submit`;
  await page.goto(submitUrl, { waitUntil: "domcontentloaded" });

  // 确保页面包含表单
  await page.waitForSelector("form#submitForm", { timeout: 15000 }).catch(() => {});

  // 写入字段（有些字段是选择器，有些需直接赋值）
  await page.evaluate(
    ({ contestId, problemIndex, languageId, sourceCode }) => {
      const langSelect = document.querySelector<HTMLSelectElement>('select[name="programTypeId"]');
      if (langSelect) langSelect.value = String(languageId);

      const idxInput = document.querySelector<HTMLInputElement>('input[name="submittedProblemIndex"]');
      if (idxInput) idxInput.value = problemIndex;

      const cIdInput = document.querySelector<HTMLInputElement>('input[name="contestId"]');
      if (cIdInput) cIdInput.value = String(contestId);

      const srcArea = document.querySelector<HTMLTextAreaElement>('textarea[name="source"]');
      if (srcArea) srcArea.value = sourceCode;

      const actionInput = document.querySelector<HTMLInputElement>('input[name="action"]');
      if (actionInput) actionInput.value = "submitSolutionFormSubmitted";
    },
    { contestId, problemIndex, languageId, sourceCode }
  );

  // 提交表单（点击提交按钮）
  const submitBtn = await page.$('input[type="submit"], button[type="submit"]');
  if (!submitBtn) throw new Error("未找到提交按钮，可能 Cookie 失效或页面结构变动");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "domcontentloaded" }),
    submitBtn.click()
  ]);
}

type SubmissionRow = {
  id: string;
  problem: string;
  verdict: string;
  time?: string;
  memory?: string;
  link?: string;
};

async function readLatestSubmissionFor(page: puppeteer.Page, handle: string, contestId: string, problemIndex: string): Promise<SubmissionRow | null> {
  const url = `https://codeforces.com/submissions/${encodeURIComponent(handle)}?my=on`;
  await page.goto(url, { waitUntil: "domcontentloaded" });

  // 表格选择器
  const row = await page.$$eval("table.status-frame-datatable tr", (rows, contestId, problemIndex) => {
    const norm = (s: string) => s.replace(/\s+/g, " ").trim();

    for (const tr of rows) {
      const tds = Array.from(tr.querySelectorAll("td"));
      if (tds.length < 7) continue;

      // 列大致：ID | When | Who | Problem | Lang | Verdict | Time | Memory ...
      const idCell = tds[0];
      const probCell = tds[3];
      const verdictCell = tds[5];
      const timeCell = tds[6];
      const memoryCell = tds[7];

      const id = norm(idCell.textContent || "");
      const problemText = norm(probCell.textContent || "");
      const verdictText = norm(verdictCell.textContent || "");

      // 问题列通常包含 "1A - Theatre Square" 或 "1A"
      // 只匹配前缀 "contestId+problemIndex"
      const expected = `${problemIndex}`.toUpperCase();
      if (!problemText.toUpperCase().startsWith(expected)) continue;

      const time = timeCell ? norm(timeCell.textContent || "") : undefined;
      const memory = memoryCell ? norm(memoryCell.textContent || "") : undefined;
      const linkEl = verdictCell.querySelector("a[href*='/submission/']");
      const link = linkEl ? (linkEl as HTMLAnchorElement).href : undefined;

      return {
        id,
        problem: problemText,
        verdict: verdictText || "Unknown",
        time,
        memory,
        link
      };
    }
    return null;
  }, contestId, problemIndex);

  return row as SubmissionRow | null;
}

function isFinalVerdict(v: string) {
  const s = v.toLowerCase();
  return (
    s.includes("accepted") ||
    s.includes("wrong answer") ||
    s.includes("time limit") ||
    s.includes("memory limit") ||
    s.includes("runtime error") ||
    s.includes("output limit") ||
    s.includes("compilation error") ||
    s.includes("skipped") ||
    s.includes("hacked") ||
    s.includes("rejected")
  );
}

export const handler: Handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    const { cookies, handle, contestId, problemIndex, languageId, sourceCode } = JSON.parse(event.body || "{}");

    if (!cookies || !handle || !contestId || !problemIndex || !languageId || !sourceCode) {
      return { statusCode: 400, body: JSON.stringify({ error: "缺少必要参数（cookies, handle, contestId, problemIndex, languageId, sourceCode）" }) };
    }

    // Netlify/Lambda Chrome 配置
    const executablePath = await chromium.executablePath();
    const browser = await puppeteer.launch({
      executablePath,
      args: chromium.args,
      headless: chromium.headless,
      defaultViewport: { width: 1280, height: 720 }
    });

    const page = await browser.newPage();
    page.setDefaultTimeout(20000);

    try {
      // 注入 Cookie（用户已通过网页手动登录并复制过）
      await setCookies(page, cookies);

      // 提交代码
      await submitSolution(page, String(contestId), String(problemIndex).toUpperCase(), String(languageId), String(sourceCode));

      // 轮询自己的提交列表，抓取最新记录
      const start = Date.now();
      const timeoutMs = 90000; // 最长 90 秒
      let latest: SubmissionRow | null = null;

      while (Date.now() - start < timeoutMs) {
        latest = await readLatestSubmissionFor(page, String(handle), String(contestId), String(problemIndex).toUpperCase());
        if (latest && latest.verdict) {
          if (isFinalVerdict(latest.verdict)) break;
        }
        // 等待后刷新
        await page.waitForTimeout(2500);
      }

      await browser.close();

      if (!latest) {
        return {
          statusCode: 200,
          body: JSON.stringify({ message: "已提交，但未能在列表中定位提交。请在 Codeforces 查看。"})
        };
      }

      return {
        statusCode: 200,
        body: JSON.stringify({
          submissionId: latest.id,
          verdict: latest.verdict,
          time: latest.time,
          memory: latest.memory,
          link: latest.link || (latest.id ? `https://codeforces.com/contest/${contestId}/submission/${latest.id}` : null)
        })
      };
    } catch (e: any) {
      await browser.close();
      return { statusCode: 500, body: JSON.stringify({ error: e?.message || String(e) }) };
    }
  } catch (err: any) {
    return { statusCode: 500, body: JSON.stringify({ error: err?.message || String(err) }) };
  }
};
