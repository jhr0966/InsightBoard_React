import type { NewsArticle } from "../api/types";
import { ageLabel } from "../lib/time";
import { gradientFor, httpsImg, newsSummary, sourceMeta } from "../lib/news";

// 뉴스 카드 — 썸네일(그라데이션 폴백)·출처 배지·상대시간·제목·요약. 클릭→원문.
export default function NewsCard({ article, compact }: { article: NewsArticle; compact?: boolean }) {
  const img = httpsImg(article.image_url);
  const meta = sourceMeta(article.source);
  const summary = newsSummary(article);
  return (
    <a className={`news-card${compact ? " news-card-compact" : ""}`} href={article.link}
      target="_blank" rel="noreferrer noopener">
      <div className="news-card-thumb" style={img ? { backgroundImage: `url(${img})` } : { background: gradientFor(article.title) }}>
        {!img && <span className="news-card-thumb-ph">{meta.label.slice(0, 1)}</span>}
      </div>
      <div className="news-card-body">
        <div className="news-card-meta">
          <span className="news-card-src" style={{ color: meta.color }}>
            <span className="news-card-dot" style={{ background: meta.color }} />{meta.label}
          </span>
          <span className="news-card-age">{ageLabel(article.collected_at || article.date)}</span>
        </div>
        <div className="news-card-title">{article.title}</div>
        {!compact && summary && <div className="news-card-sum">{summary}</div>}
      </div>
    </a>
  );
}
