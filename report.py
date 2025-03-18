from openai import OpenAI
import time
import os
import socket
import paramiko
import yaml
from ollama import Client
from concurrent.futures import ThreadPoolExecutor
import subprocess

# 系统巡检命令列表，新增了硬件监控、日志审计等检查项
commands = [
    "uname -a", "hostname", "cat /etc/os-release", "lsb_release -a", "uptime",
    "lspci", "lsusb", "lsblk",
    "ss -tunlp", "ip addr",
    "df -Th", "lsblk", "mount",
    "last", "who", "cat /etc/passwd", "cat /etc/sudoers", "sudo iptables -nvL", "sudo firewall-cmd --list-all",
    "systemctl list-units --type=service --no-pager",
    "crontab -l", "date", "timedatectl",
    "top -bc -o %MEM | head -n 17|sed -n '7,17p'", 
    "top -bc -o %CPU | head -n 17|sed -n '7,17p'",
    # 新增的检查项
    "free -m",  # 内存使用情况
    "vmstat 1 5",  # 内存与交换区使用情况
   "sudo journalctl -p 3 -n 50",   # 查看最近 50 条错误级别日志
   "sudo dmesg | tail -n 20",       # 查看最近 20 条内核日志
   "sudo grep -i 'error|fail' /var/log/syslog",  # 查找系统日志中的错误
   "sudo find /var/log -type f -size +50M -exec du -h {} + | sort -rh",  # 查找大于50M的日志文件
   "sudo systemctl list-units --failed",  # 列出失败的服务
   "sudo journalctl -u sshd --no-pager | tail -n 20",   # 检查 SSHD 日志
   "nvidia-smi",
]

# AI分析系统提示模板
AI_PROMPT = """你是一名拥有 RHCE/CCIE/HCIE/H3CSE 认证的高级工程师，请根据以下服务器配置信息进行专业分析：

要求：
1. 识别系统类型（CentOS/Ubuntu等发行版）
2. 解析关键配置参数：
   - 网络配置（IP地址、开放端口）
   - 存储情况（磁盘使用率、挂载点）
   - 安全设置（防火墙规则、sudo权限）
   - 服务状态（异常服务、高危进程）
   - 系统日志的错误分析
   
3. 检测潜在问题：
   - 安全漏洞（弱密码、权限问题）
   - 性能瓶颈（CPU/内存使用率）
   - 配置错误（服务冲突、失效策略）
   - 日志审计（错误日志、内核日志）

4. 生成HTML格式报告：
   - 包含完整的HTML文档结构
   - 使用表格展示关键指标（带边框样式）
   - 高危问题用红色标记
   - 包含基本CSS样式
   - 服务器总结以及优化建议

5. 如果有 nvidia-smi 命令，请分析显卡使用情况
<!DOCTYPE html>
<html>
<head>
  <title>服务器健康检查报告（{ip}）</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; }}
    table {{ border-collapse: collapse; width: 80%; margin: 20px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #f8f9fa; }}
    .critical {{ color: red; font-weight: bold; }}
    .section {{ margin-bottom: 30px; }}
  </style>
</head>
<body>
  <div class="section">
    <h1>服务器健康检查报告（{ip}）</h1>

    <div class="section">
      <h2>系统概览</h2>
      <ul>
        <li>操作系统：</li>
        <li>运行时间：</li>
        <li>最后登录用户：</li>
      </ul>
    </div>

    <div class="section">
      <h2>关键问题</h2>
      <ol>
        <li>安全风险（按严重性排序）
          <ul>
            <li class="critical">高危漏洞示例</li>
          </ul>
        </li>
        <li>性能问题</li>
        <li>配置异常</li>
        <li>系统日志错误分析</li>
      </ol>
    </div>

    <div class="section">
      <h2>优化建议</h2>
      <ul>
        <li>分点列出可执行方案</li>
      </ul>
    </div>

    <div class="section">
      <h2>详细指标</h2>
      <table>
        <tr>
          <th>检查项</th>
          <th>状态</th>
          <th>建议</th>
        </tr>
        <tr>
          <td>CPU使用率</td>
          <td>85%</td>
          <td class="critical">需要优化</td>
        </tr>
      </table>
    </div>
  </div>
</body>
</html>

现在开始分析以下配置信息：
"""

# 新增的命令和功能检查
def run_command_with_sudo(command):
    """执行命令并以超级用户权限运行"""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()
        return stdout.decode(), stderr.decode()
    except Exception as e:
        return None, str(e)

def AI_V3(log_file, ipadd, api_key, base_url, model):
    """Deepseek 引擎AI分析"""
    # 从日志文件名中提取时间戳
    log_filename = os.path.basename(log_file)  # 获取日志文件名
    timestamp = log_filename.split('_')[-1].replace('.log', '')  # 提取时间戳部分
    
    # 读取日志文件内容
    with open(log_file, 'r', encoding='utf-8') as f:
        data = f.read()

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": AI_PROMPT.format(ip=ipadd)},
            {"role": "user", "content": data},
        ],
        stream=True,
        temperature=0.3,
        max_tokens=30000
    )

    filename = os.path.join(dir_url, f"{ipadd}_analysis_{timestamp}.html")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            content_buffer = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    content_buffer += content
            
            # 处理内容，去除 Markdown 代码块标记
            processed_content = content_buffer
            if processed_content.startswith("```html"):
                processed_content = processed_content[7:]
            if processed_content.endswith("```"):
                processed_content = processed_content[:-3]
            
            f.write(processed_content)
        return filename
    except Exception as e:
        print(f"AI分析失败: {str(e)}")
        return None

def local_ollama(data, ipadd):
    """本地大模型分析"""
    client = Client(host='http://localhost:11434')

    try:
        response = client.generate(
            model='qwen:1.8b',
            system=AI_PROMPT.format(ip=ipadd),
            prompt=data,
            options={'temperature': 0.5},
            stream=True
        )

        filename = os.path.join(dir_url, f"{ipadd}_local_analysis.html")
        with open(filename, 'w', encoding='utf-8') as f:
            for chunk in response:
                if chunk['response']:
                    content = chunk['response']
                    print(content, end='', flush=True)
                    f.write(content)
                    time.sleep(0.02)
        return filename
    except Exception as e:
        print(f"本地模型异常: {str(e)}")
        return None

def inspect_server(ip_address, user, passwd, sudo_pass, port, max_retries=3):
    """执行服务器巡检"""
    for attempt in range(max_retries):
        try:
            print(f"[{ip_address}] 尝试连接 (第{attempt + 1}次)...")
            # 验证IP有效性
            socket.inet_aton(ip_address)

            # SSH连接配置
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=ip_address,
                port=port,
                username=user,
                password=passwd,
                timeout=15,
                banner_timeout=20,
                allow_agent=False,
                look_for_keys=False
            )
            print(f"[{ip_address}] 连接成功")

            # 生成报告文件
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = os.path.join(dir_url, f"inspection_{ip_address}_{timestamp}.log")

            with open(filename, 'w', encoding='utf-8') as report:
                # 写入报告头
                report.write(f"=== Server Inspection Report ===\n")
                report.write(f"IP Address: {ip_address}\n")
                report.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                report.write(f"Inspector: {user}\n\n")

                # 执行所有检查命令
                for idx, cmd in enumerate(commands, 1):
                    try:
                        report.write(f"[{idx}/{len(commands)}] Executing: {cmd}\n")

                        # 先尝试普通权限执行命令
                        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
                        exit_code = stdout.channel.recv_exit_status()
                        output = stdout.read().decode('utf-8').strip()
                        error = stderr.read().decode('utf-8').strip()

                        # 如果命令执行失败且提供了sudo密码，尝试使用sudo重试
                        if exit_code != 0 and sudo_pass:
                            report.write(f"\nCommand failed with exit code {exit_code}, retrying with sudo...\n")
                            sudo_cmd = f'echo "{sudo_pass}" | sudo -S {cmd}'
                            stdin, stdout, stderr = client.exec_command(sudo_cmd, timeout=10)
                            exit_code = stdout.channel.recv_exit_status()
                            output = stdout.read().decode('utf-8').strip()
                            error = stderr.read().decode('utf-8').strip()

                        # 记录结果
                        report.write(f"Exit Code: {exit_code}\n")
                        if output:
                            report.write(f"Output:\n{output}\n")
                        if error:
                            report.write(f"Error:\n{error}\n")
                            # 如果使用sudo失败，尝试不使用sudo重新执行
                            if sudo_pass and 'sudo' in error:
                                report.write(f"\nRetrying without sudo...\n")
                                stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
                                exit_code = stdout.channel.recv_exit_status()
                                output = stdout.read().decode('utf-8').strip()
                                error = stderr.read().decode('utf-8').strip()
                                report.write(f"Exit Code: {exit_code}\n")
                                if output:
                                    report.write(f"Output:\n{output}\n")
                                if error:
                                    report.write(f"Error:\n{error}\n")
                        report.write("-"*60 + "\n\n")

                    except paramiko.SSHException as e:
                        report.write(f"Command failed: {str(e)}\n\n")
                    except socket.timeout:
                        report.write("Command timeout\n\n")

            client.close()
            return filename

        except paramiko.AuthenticationException:
            print(f"[{ip_address}] SSH认证失败")
        except socket.timeout:
            print(f"[{ip_address}] 连接超时")
        except paramiko.SSHException as e:
            print(f"[{ip_address}] SSH错误: {str(e)}")
        except Exception as e:
            print(f"[{ip_address}] 未知错误: {str(e)}")

        if attempt < max_retries - 1:
            time.sleep(5)  # 等待5秒后重试
            continue
        break

    return None

def validate_config(ssh_user, ssh_pass, volc_key):
    """验证配置参数"""
    if not ssh_user or not ssh_pass:
        raise ValueError("SSH用户名和密码不能为空")
    if not volc_key:
        print("警告: 未配置Deepseek API密钥，将使用本地模型进行分析")

def process_server(ip, ssh_user, ssh_pass, ssh_port, volc_key, base_url, model):
    """处理单个服务器的巡检任务"""
    print(f"\n{'='*40}")
    print(f"开始处理服务器: {ip}")

    try:
        # 第一步：执行巡检
        log_file = inspect_server(ip, ssh_user, ssh_pass, ssh_pass, ssh_port)
        if not log_file:
            print(f"服务器 {ip} 巡检失败")
            return

        # 第二步：AI分析
        with open(log_file, 'r', encoding='utf-8') as f:
            raw_data = f.read()

        analysis_file = None
        if volc_key:  # 优先使用Deepseek引擎
            print("\n使用Deepseek引擎分析...")
            analysis_file = AI_V3(log_file, ip, volc_key, base_url, model)  # 传入日志文件路径而不是内容
        else:  # 备用本地模型
            print("\n使用本地模型分析...")
            analysis_file = local_ollama(raw_data, ip)

        # 清理临时文件
        if analysis_file and os.path.exists(analysis_file):
            # os.remove(log_file)
            print(f"\n分析报告保存至: {analysis_file}")
        else:
            print("分析失败，保留原始日志")

    except Exception as e:
        print(f"处理异常: {str(e)}")
    finally:
        print(f"{'='*40}\n")

def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"配置文件加载失败: {str(e)}")
        return None

def main():
    global dir_url
    
    # 加载配置文件
    config = load_config()
    if not config:
        return

    # 初始化输出目录
    dir_url = os.path.abspath(config['output']['dir'])
    os.makedirs(dir_url, exist_ok=True)

    # 获取全局SSH配置
    global_ssh = config['ssh']
    
    # 获取AI配置
    volc_key = config['ai'].get('volc_key', '')
    base_url = config['ai'].get('base_url', 'https://api.deepseek.com')
    model = config['ai'].get('model', 'deepseek-chat')

    # 处理每个服务器
    devices = []
    ssh_configs = {}
    
    for server in config['servers']:
        ip = server['ip']
        devices.append(ip)
        
        # 合并服务器特定的SSH配置和全局配置
        server_ssh = server.get('ssh', {})
        ssh_configs[ip] = {
            'port': server_ssh.get('port', global_ssh['port']),
            'user': server_ssh.get('user', global_ssh['user']),
            'password': server_ssh.get('password', global_ssh['password'])
        }

    # 使用线程池并发执行巡检任务
    with ThreadPoolExecutor(max_workers=min(len(devices), 5)) as executor:
        futures = []
        for ip in devices:
            ssh_config = ssh_configs[ip]
            futures.append(executor.submit(
                process_server,
                ip,
                ssh_config['user'],
                ssh_config['password'],
                ssh_config['port'],
                volc_key,
                base_url,
                model
            ))
        
        # 等待所有任务完成
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"任务执行异常: {str(e)}")



def test_AI():
    global dir_url
    config = load_config()
    if not config:
        return

    # 初始化输出目录
    dir_url = os.path.abspath(config['output']['dir'])
    os.makedirs(dir_url, exist_ok=True)
    
    # 获取AI配置
    volc_key = config['ai'].get('volc_key', '')
    base_url = config['ai'].get('base_url', 'https://api.deepseek.com')
    model = config['ai'].get('model', 'deepseek-chat')

    # 使用 dir_url 构建日志文件路径
    log_file = os.path.join(dir_url, "inspection_47.57.186.97_20250317-171050.log")
    with open(log_file, 'r', encoding='utf-8') as f:
        raw_data = f.read()

    analysis_file = None
    if volc_key:  # 优先使用Deepseek引擎
        print("\n使用Deepseek引擎分析...")
        analysis_file = AI_V3(log_file, "47.57.186.97", volc_key, base_url, model)


if __name__ == '__main__':
    main()
    # test_AI()