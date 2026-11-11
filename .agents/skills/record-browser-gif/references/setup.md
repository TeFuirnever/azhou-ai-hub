# 工具与编码

运行依赖：Python 3.10+；PATH 中的 ffmpeg 与 ffprobe，须支持 WebM、GIF、trim、setpts、fps、scale、tpad、palettegen/paletteuse 及 JSON probe。没有声明一个未经测试的 ffmpeg 最低版本；先运行下面的能力检查。依赖缺失时报告，不能擅自安装/升级。浏览器录制由当前宿主实际能力提供，编码器本身不负责操作浏览器。

```sh
python3 --version
ffmpeg -version
ffprobe -version
python3 /absolute/path/to/record-browser-gif/scripts/encode_gif.py --help
```

用获授权、已忽略的单次输出目录，输入和输出使用绝对路径。以下路径和区间是占位示例，执行时替换为实际观察值。

## 连续视频

```sh
python3 /absolute/path/to/record-browser-gif/scripts/encode_gif.py \
  /absolute/path/to/demo.webm /absolute/path/to/demo.gif \
  --start 2 --end 32 --speed 2 --final-hold 3 \
  --fps 10 --max-width 1200 --colors 128
```

省略区间/速度时保留完整视频、1 倍速并追加 2 秒末帧。start/end 取实际媒体时间而非猜测墙钟。至少覆盖两个输出帧；提高 fps 不能恢复没录到的动作。

## 截图序列

```sh
python3 /absolute/path/to/record-browser-gif/scripts/encode_gif.py \
  /absolute/path/to/frames /absolute/path/to/demo.gif \
  --pattern '*.png' --durations 1.5,1.5,1.5,3.5 \
  --fps 10 --max-width 1200 --colors 128
```

目录按文件名排序，至少两张同尺寸图。durations 可用一个正数适用于所有帧，或每帧一个；最后状态留够阅读时间。start/end/speed/final-hold 只用于视频，pattern/durations 只用于目录。

## 校验与限制

编码器拒绝非法/非有限数值、空/越界区间、少于两帧、混用模式参数、尺寸不一致、错误 duration 数量、默认覆盖已有输出；检查 fps≤30、4–256 色、宽度、动画帧数、时长及默认 5 MiB 上限。失败退出非零，成功输出 JSON。

默认不覆盖；只有确认具体输出可替换才用 `--force`。编码后发现超限等问题可能留下未合格 GIF，不要发布它。先减尺寸，再降颜色/fps，但必须可读；仍过大就把同一运行切成连续、不重叠的编号部分，各自检查并标明位置/区间。

运行记录保留具体 Python/ffmpeg/ffprobe 版本、命令和结果。回归可用同一 encoder 的上游媒体测试，测试材料放在任务证据而不是安装运行包；测试成功不证明真实浏览器录制或人工视觉批准。
