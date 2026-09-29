using System;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;

namespace AdminPanelFlyModeFix
{
    // Plain data contracts keep Unity's serializer and engine object graphs out of reports.
    [DataContract] internal struct Point
    {
        [DataMember] public float x, y, z;
        internal Point(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    }

    [DataContract] internal sealed class Report
    {
        [DataMember] public string utc, save, guard, game, pluginVersion;
        [DataMember] public bool recovering, playerGroundLoaded;
        [DataMember] public float gameTime, timeScale;
        [DataMember] public int zombies, unsupported, stableCandidates, repaired;
        [DataMember] public Point player, worldOrigin;
        [DataMember(IsRequired = true)] public Row[] rows;
    }

    [DataContract] internal sealed class Row
    {
        [DataMember] public int id, layer, groundLayer, groundMask;
        [DataMember] public string name, state, collider, exclusion, observation, constraints, parent;
        [DataMember] public Point position, worldPosition, transformPosition, velocity, momentum, lastValidPosition;
        [DataMember] public Point visualPosition, modelPosition, headPosition;
        [DataMember] public float gravity, clearance, groundY, rayLength, upright;
        [DataMember] public bool groundFound, grounded, kinematic, fallen, registered, candidate, alive, eligible;
        [DataMember] public bool controllerEnabled, npcEnabled, safeScene, collisionEnabled, sleeping, builtInGravity;
        [DataMember] public bool hasVisual, hasModel, hasHead;
        [DataMember] public TraceSample trace;
    }

    [DataContract] internal sealed class TraceSample
    {
        [DataMember] public int fixedCalls, antiFallCalls, antiFallMoves;
        [DataMember] public float lastFixedTime = -1, lastAntiFallTime = -1, lastAntiFallMoveTime = -1;
        [DataMember] public float lastAntiFallBeforeY, lastAntiFallAfterY;
    }

    [DataContract] internal sealed class RecoveryEvent
    {
        [DataMember] public string phase, utc, save;
        [DataMember(IsRequired = true)] public Row before;
        [DataMember] public Point target;
    }

    internal static class DiagnosticJson
    {
        internal static string Serialize<T>(T value)
        {
            using (var stream = new MemoryStream())
            {
                new DataContractJsonSerializer(typeof(T)).WriteObject(stream, value);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        internal static Report ReadReport(string json)
        {
            using (var stream = new MemoryStream(Encoding.UTF8.GetBytes(json)))
            {
                var report = (Report)new DataContractJsonSerializer(typeof(Report)).ReadObject(stream);
                if (report?.rows == null || report.rows.Length != report.zombies)
                    throw new SerializationException("Diagnostic report is missing zombie rows or has the wrong row count.");
                return report;
            }
        }

        internal static string CompleteReport(Report report)
        {
            string json = Serialize(report);
            ReadReport(json); // Refuse to publish a summary-only report, including on the game runtime.
            return json;
        }

        internal static void WriteReport(string folder, Report report)
        {
            string json = CompleteReport(report);
            string path = Path.Combine(folder, "latest.json"), pending = path + ".tmp";
            File.WriteAllText(pending, json);
            if (File.Exists(path)) File.Replace(pending, path, null);
            else File.Move(pending, path);
            string history = Path.Combine(folder, "history.jsonl");
            if (File.Exists(history) && new FileInfo(history).Length > 8 * 1024 * 1024)
            {
                string previous = Path.Combine(folder, "history.previous.jsonl");
                if (File.Exists(previous)) File.Delete(previous);
                File.Move(history, previous);
            }
            File.AppendAllText(history, json + Environment.NewLine);
        }
    }
}
