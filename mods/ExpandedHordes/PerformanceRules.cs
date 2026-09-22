using System;

namespace ExpandedHordes
{
    // Bounded storage, no per-frame allocations. The percentile covers up to the first
    // 8,192 frames in each reporting window; mean/max cover every accepted frame.
    internal sealed class FrameWindow
    {
        private readonly double[] samples = new double[8192];
        private readonly double[] sorted = new double[8192];
        internal int Count { get; private set; }
        internal int SampleCount { get; private set; }
        internal double Total { get; private set; }
        internal double Maximum { get; private set; }
        internal double Mean => Count == 0 ? 0 : Total / Count;
        internal void Add(double milliseconds)
        {
            if (!(milliseconds > 0) || double.IsInfinity(milliseconds)) return;
            Count++; Total += milliseconds; Maximum = Math.Max(Maximum, milliseconds);
            if (SampleCount < samples.Length) samples[SampleCount++] = milliseconds;
        }
        internal double Percentile95()
        {
            if (SampleCount == 0) return 0;
            Array.Copy(samples, sorted, SampleCount);
            Array.Sort(sorted, 0, SampleCount);
            return sorted[(int)Math.Ceiling(SampleCount * 0.95) - 1];
        }
        internal void Reset() { Count = SampleCount = 0; Total = Maximum = 0; }
    }

    internal static class PerformanceRules
    {
        internal static string Hint(double cpu, double gpu, double wait, double frame)
        {
            if (!(cpu > 0) || !(gpu > 0) || double.IsInfinity(cpu) || double.IsInfinity(gpu)) return "unavailable";
            if (wait > 0.5 && cpu < frame * 0.8 && gpu < frame * 0.8) return "presentation_limit_suspected";
            if (cpu > gpu * 1.2) return "CPU_heavier";
            if (gpu > cpu * 1.2) return "GPU_heavier";
            return "similar_CPU_GPU";
        }
    }
}
