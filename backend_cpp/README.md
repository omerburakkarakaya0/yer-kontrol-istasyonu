# C++ Telemetry Bridge

This bridge reads MAVLink telemetry outside the PyQt process and emits one JSON
object per line on stdout. Python consumes it through `CppTelemetryBackend`.

Build on Windows after installing Visual Studio Build Tools or CMake + a C++ compiler:

```powershell
cmake -S backend_cpp -B backend_cpp/build
cmake --build backend_cpp/build --config Release
```

Expected executable:

```text
backend_cpp/build/telemetry_bridge.exe
```

Until the executable exists, the Python app automatically falls back to the
existing Python MAVLink backend.
