import fetch from "node-fetch";

export default async (req: any, res: any) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { problem, source, langId, jsessionid, c39ce7 } = req.body;

    // 拼接 cookie
    const cookie = `JSESSIONID=${jsessionid}; 39ce7=${c39ce7}`;

    // 提交代码
    const submitResp = await fetch("https://codeforces.com/problemset/submit", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie
      },
      body: new URLSearchParams({
        csrf_token: c39ce7,  // 有时要伪造 token，这里简化
        action: "submitSolutionFormSubmitted",
        submittedProblemCode: problem,
        source,
        programTypeId: langId,
        tabSize: "4",
        sourceFile: ""
      })
    });

    if (submitResp.status !== 200) {
      return res.status(500).json({ error: "提交失败，状态码: " + submitResp.status });
    }

    return res.json({ message: "提交成功！请在 Codeforces 查看结果" });

  } catch (err: any) {
    return res.status(500).json({ error: err.message });
  }
};
