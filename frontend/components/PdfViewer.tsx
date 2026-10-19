"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import {
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  Minus,
  Plus,
} from "lucide-react";

export function PdfViewer({
  url,
  initialPage = 1,
}: {
  url: string;
  initialPage?: number;
}) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(initialPage),
    [width, setWidth] = useState(700),
    [zoom, setZoom] = useState(1),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null),
    viewport = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    let destroy: (() => void) | undefined;
    setLoading(true);
    setError("");
    setDocument(null);
    void import("pdfjs-dist")
      .then(async (pdfjs) => {
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const task = pdfjs.getDocument({ url, enableXfa: false });
        destroy = () => {
          void task.destroy();
        };
        const pdf = await task.promise;
        if (active) {
          setDocument(pdf);
          setPage(Math.min(Math.max(initialPage, 1), pdf.numPages));
        }
      })
      .catch((e) => {
        if (active) {
          setError(e instanceof Error ? e.message : "PDF 加载失败");
          setLoading(false);
        }
      });
    return () => {
      active = false;
      destroy?.();
    };
  }, [url, initialPage]);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(240, entries[0].contentRect.width - 30)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!document || !canvas.current) return;
    let active = true;
    let render: RenderTask | undefined;
    setLoading(true);
    void document
      .getPage(page)
      .then((pdfPage) => {
        if (!active || !canvas.current) return;
        const base = pdfPage.getViewport({ scale: 1 }),
          view = pdfPage.getViewport({ scale: (width / base.width) * zoom });
        const ratio = Math.min(window.devicePixelRatio || 1, 2),
          target = canvas.current;
        target.width = Math.floor(view.width * ratio);
        target.height = Math.floor(view.height * ratio);
        target.style.width = `${view.width}px`;
        target.style.height = `${view.height}px`;
        const context = target.getContext("2d");
        if (!context) throw new Error("Canvas 不可用");
        render = pdfPage.render({
          canvas: target,
          canvasContext: context,
          viewport: view,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        });
        return render.promise;
      })
      .then(() => {
        if (active) setLoading(false);
      })
      .catch((e) => {
        if (active) {
          setError(e instanceof Error ? e.message : "页面渲染失败");
          setLoading(false);
        }
      });
    return () => {
      active = false;
      render?.cancel();
    };
  }, [document, page, width, zoom]);
  return (
    <div className="pdf-viewer">
      <div className="pdf-controls">
        <button
          aria-label="上一页"
          disabled={!document || page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <label>
          第{" "}
          <input
            aria-label="PDF 页码"
            type="number"
            min={1}
            max={document?.numPages || 1}
            value={page}
            onChange={(e) => {
              const next = Number(e.target.value);
              if (
                Number.isInteger(next) &&
                next >= 1 &&
                document &&
                next <= document.numPages
              )
                setPage(next);
            }}
          />{" "}
          / {document?.numPages || "—"} 页
        </label>
        <button
          aria-label="下一页"
          disabled={!document || page >= document.numPages}
          onClick={() => setPage((p) => p + 1)}
        >
          <ChevronRight size={16} />
        </button>
        <span />
        <button
          aria-label="缩小论文"
          disabled={zoom <= 0.5}
          onClick={() => setZoom((z) => z - 0.25)}
        >
          <Minus size={15} />
        </button>
        <small>{Math.round(zoom * 100)}%</small>
        <button
          aria-label="放大论文"
          disabled={zoom >= 2}
          onClick={() => setZoom((z) => z + 0.25)}
        >
          <Plus size={15} />
        </button>
        <a href={`${url}#page=${page}`} target="_blank" rel="noreferrer">
          打开原文件
        </a>
      </div>
      <div className="pdf-canvas-scroll" ref={viewport}>
        {loading && (
          <div className="pdf-loading">
            <LoaderCircle className="spin" size={18} />
            渲染论文第 {page} 页…
          </div>
        )}
        {error && (
          <p role="alert" className="notice">
            PDF.js: {error}
          </p>
        )}
        <canvas
          ref={canvas}
          aria-label={`论文原文第 ${page} 页`}
          data-rendered={!loading && !error}
        />
      </div>
    </div>
  );
}
