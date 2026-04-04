import katex from "katex";

const FORMULA_KEYWORD_PATTERN =
  /\b(?:pr\(|pr\(>\|[tz]\|\)|rss|null deviance|residual deviance|aic:|theta:|std\. err\.|e\[[^\]]+\]|glm\(|anova\(|normal\(|poisson\(|binomial\(|logit\(|pchisq|x\s*beta)\b/i;

const EQUATION_SYMBOL_PATTERN = /[=~\u223c\u2248\u2264\u2265\u03bc\u03c3\u03b2\u03c7\u0394\u03bb]/i;

const STRUCTURED_FORMULA_PATTERN =
  /(?:\b[a-z]\d*\s*=|\b(?:mu|logit|normal|poisson|binomial)\s*\(|\bx\s*beta\b|\u03c3\^?2|\u03c3\u00b2|\u03c7(?:2|\u00b2)|e\[[^\]]+\]|[Ii]_?n|x\u03b2)/i;

type AnswerContentProps = {
  text: string;
};

type AnswerBlock =
  | { type: "spacer"; key: string }
  | { type: "text"; key: string; content: string }
  | { type: "math"; key: string; content: string };

function looksLikeFormulaLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) {
    return false;
  }
  if (trimmed.startsWith(">")) {
    return true;
  }
  if (EQUATION_SYMBOL_PATTERN.test(trimmed) && STRUCTURED_FORMULA_PATTERN.test(trimmed)) {
    return true;
  }
  return FORMULA_KEYWORD_PATTERN.test(trimmed);
}

function normalizePlainFormula(line: string): string {
  return line
    .trim()
    .replace(/^\-\s*/, "")
    .replace(/^\d+\)\s*/, "")
    .replace(/[∼~]/g, " \\sim ")
    .replace(/…|\.\.\./g, " \\ldots ")
    .replace(/≤/g, " \\le ")
    .replace(/≥/g, " \\ge ")
    .replace(/μ̂/g, "\\hat{\\mu}")
    .replace(/σ̂/g, "\\hat{\\sigma}")
    .replace(/β(\d+)/g, "\\beta_{$1}")
    .replace(/μ([a-z0-9])/gi, "\\mu_{$1}")
    .replace(/σ([a-z0-9])/gi, "\\sigma_{$1}")
    .replace(/π([a-z0-9])/gi, "\\pi_{$1}")
    .replace(/χ([a-z0-9])/gi, "\\chi_{$1}")
    .replace(/\bVar\s*\(/g, "\\operatorname{Var}(")
    .replace(/\bBinomial\s*\(/g, "\\operatorname{Binomial}(")
    .replace(/\bNormal\s*\(/g, "\\operatorname{Normal}(")
    .replace(/\bPoisson\s*\(/g, "\\operatorname{Poisson}(")
    .replace(/\blogit\s*\(/g, "\\operatorname{logit}(")
    .replace(/\bsqrt\s*\(/g, "\\sqrt(")
    .replace(/\|/g, " \\mid ");
}

function renderMath(content: string): string | null {
  const source = content.trim();
  if (!source) {
    return null;
  }
  try {
    return katex.renderToString(source, {
      displayMode: true,
      throwOnError: false,
      strict: "ignore",
    });
  } catch {
    return null;
  }
}

function parseBlocks(text: string): AnswerBlock[] {
  const lines = text.split(/\r?\n/);
  const blocks: AnswerBlock[] = [];
  const mathBuffer: string[] = [];
  let inMathBlock = false;

  const flushMathBuffer = (key: string) => {
    const joined = mathBuffer.join("\n").trim();
    mathBuffer.length = 0;
    if (joined) {
      blocks.push({ type: "math", key, content: joined });
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (trimmed === "$$") {
      if (inMathBlock) {
        flushMathBuffer(`math-${index}`);
      }
      inMathBlock = !inMathBlock;
      return;
    }

    if (trimmed.startsWith("$$") && trimmed.endsWith("$$") && trimmed.length > 4) {
      blocks.push({
        type: "math",
        key: `math-inline-${index}`,
        content: trimmed.slice(2, -2).trim(),
      });
      return;
    }

    if (inMathBlock) {
      mathBuffer.push(trimmed);
      return;
    }

    if (!trimmed) {
      blocks.push({ type: "spacer", key: `spacer-${index}` });
      return;
    }

    if (looksLikeFormulaLine(trimmed)) {
      blocks.push({
        type: "math",
        key: `formula-${index}`,
        content: normalizePlainFormula(trimmed),
      });
      return;
    }

    blocks.push({ type: "text", key: `text-${index}`, content: trimmed });
  });

  if (inMathBlock) {
    flushMathBuffer(`math-tail-${blocks.length}`);
  }

  return blocks;
}

export function AnswerContent({ text }: AnswerContentProps) {
  const blocks = parseBlocks(text);

  return (
    <div className="space-y-3">
      {blocks.map((block) => {
        if (block.type === "spacer") {
          return <div key={block.key} className="h-1" />;
        }

        if (block.type === "text") {
          return (
            <p key={block.key} className="whitespace-pre-wrap text-sm leading-7 text-ink-800">
              {block.content}
            </p>
          );
        }

        const rendered = renderMath(block.content);
        if (!rendered) {
          return (
            <pre
              key={block.key}
              className="overflow-x-auto rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm leading-7 text-ink-900 shadow-sm"
            >
              <code>{block.content}</code>
            </pre>
          );
        }

        return (
          <div
            key={block.key}
            className="math-block w-full max-w-full overflow-x-auto overflow-y-hidden rounded-2xl border border-ink-200 bg-white px-4 py-4 text-ink-900 shadow-sm"
            dangerouslySetInnerHTML={{ __html: rendered }}
          />
        );
      })}
    </div>
  );
}
