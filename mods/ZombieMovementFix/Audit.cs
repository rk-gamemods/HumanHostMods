using System;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;

namespace ZombieMovementFix
{
    [DataContract] internal struct Position
    {
        [DataMember] public float x, y, z;
        internal Position(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    }

    [DataContract] internal sealed class Record
    {
        [DataMember] public string phase, utc, save, name, detail;
        [DataMember] public int id, generation, spawnSource;
        [DataMember] public float gameTime;
        [DataMember] public Position position, velocity, target, worldOrigin;
        [DataMember] public MovementState state;
    }

    [DataContract] internal sealed class Summary
    {
        [DataMember] public string utc, save, version = "0.1.0";
        [DataMember] public int checkedZombies, missingMovement, repaired;
        [DataMember] public Record[] unresolved;
    }

    internal sealed class Audit
    {
        private readonly string folder;
        internal Audit(string folder) { this.folder = folder; Directory.CreateDirectory(folder); }
        internal static string Serialize<T>(T value)
        {
            using (var stream = new MemoryStream())
            {
                new DataContractJsonSerializer(typeof(T)).WriteObject(stream, value);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        // Failure propagates to the caller: no write-ahead record means no repair.
        internal void Append(Record record)
        {
            string path = Path.Combine(folder, "events.jsonl");
            if (File.Exists(path) && new FileInfo(path).Length >= 8 * 1024 * 1024)
            {
                string previous = Path.Combine(folder, "events.previous.jsonl");
                if (File.Exists(previous)) File.Delete(previous);
                File.Move(path, previous);
            }
            File.AppendAllText(path, Serialize(record) + Environment.NewLine);
        }

        internal void WriteSummary(Summary summary)
        {
            string path = Path.Combine(folder, "latest.json"), temp = path + ".tmp";
            File.WriteAllText(temp, Serialize(summary));
            if (File.Exists(path)) File.Replace(temp, path, null);
            else File.Move(temp, path);
        }
    }
}
