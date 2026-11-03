export default function VideoFactoryPage() {
  return (
    <div className="min-h-screen bg-[#080704] px-4 pb-8 pt-24 text-stone-100 md:px-6 xl:px-10">
      <section className="mx-auto mb-5 flex w-full max-w-[1720px] items-center justify-between gap-4 rounded-[26px] border border-white/10 bg-[#0d1219] px-5 py-4 shadow-[0_18px_60px_rgba(0,0,0,0.35)]">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-amber-200/70">百骑谱视频制作台</p>
          <h1 className="mt-2 text-2xl font-semibold text-stone-50 md:text-3xl">视频制作画布</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <a
            href="/"
            className="inline-flex items-center rounded-full border border-white/12 bg-white/[0.04] px-4 py-2 text-sm text-stone-200 transition hover:border-amber-200/30 hover:text-amber-100"
          >
            返回首页
          </a>
          <a
            href="/workflow-studio/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-full bg-amber-300 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-200"
          >
            新窗口打开
          </a>
        </div>
      </section>
      <section className="mx-auto w-full max-w-[1720px]">
        <iframe
          src="/workflow-studio/"
          title="视频制作流程"
          className="block h-[calc(100vh-190px)] min-h-[660px] w-full rounded-[28px] border border-white/10 bg-[#0b0f15] shadow-[0_24px_80px_rgba(0,0,0,0.35)]"
        />
      </section>
    </div>
  );
}
