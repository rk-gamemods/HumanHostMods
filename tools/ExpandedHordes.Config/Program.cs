using System;
using System.IO;
using BepInEx;
using BepInEx.Configuration;
using ExpandedHordes;

if (args.Length != 1) throw new ArgumentException("Pass the destination .cfg path.");
string path = Path.GetFullPath(args[0]);
bool existed = File.Exists(path);
var config = new ConfigFile(path, false,
    new BepInPlugin(ModIdentity.Guid, ModIdentity.Name, ModIdentity.Version));
config.SaveOnConfigSet = false;
ModSettings.Bind(config);
config.Save();
var readback = new ConfigFile(path, false);
readback.SaveOnConfigSet = false;
ModSettings.Bind(readback);
if (readback.Count != 16)
    throw new InvalidDataException("Generated config failed BepInEx readback.");
foreach (var entry in config)
    if (!Equals(entry.Value.BoxedValue, readback[entry.Key].BoxedValue))
        throw new InvalidDataException($"Config readback changed {entry.Key}.");
if (!File.ReadAllText(path).StartsWith($"## Settings file was created by plugin {ModIdentity.Name} v{ModIdentity.Version}", StringComparison.Ordinal))
    throw new InvalidDataException("BepInEx readback removed the HHMM display-name header.");
Console.WriteLine($"{(existed ? "Refreshed descriptions/ranges and retained accepted values for" : "Created")} {readback.Count} verified BepInEx settings: {path}");
