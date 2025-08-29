import fetch from "node-fetch";
import * as cheerio from "cheerio";

export default async (req: any, res: any) => {
  const { handle } = req.query;

  if (!handle) return res.status(400).json({ error: "缺少 handle 参数" });

  try {
    const page = await fetch(`https://codeforces.com/submissions/${handle}`);
    const html = await page.text();
    const $ = cheerio.load(html);

    const firstRow = $("table.status-frame-datatable tr").eq(1);
    const submissionId = firstRow.find("td").eq(0).text().trim();
    const verdict = firstRow.find("td").eq(5).text().trim();

    return res.json({ submissionId, verdict });

  } catch (err: any) {
    return res.status(500).json({ error: err.message });
  }
};
