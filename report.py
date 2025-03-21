from openai import OpenAI
# 修复了字符串格式化问题：将AI_PROMPT中的{ip}改为{{ip}}并使用replace替代format
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
    # 系统基本信息
    "uname -a",                                     # 显示完整的系统信息（内核版本、主机名、架构等）
    "hostname",                                     # 显示当前主机名
    "cat /etc/os-release",                          # 显示Linux发行版信息
    "uptime",                                       # 显示系统运行时间、用户数和平均负载
    
    # 硬件信息
    "lspci",                                        # 列出所有PCI总线设备
    "lsusb",                                        # 列出所有USB设备
    "lsblk",                                        # 以树状结构显示块设备信息
    "df -Th",                                       # 显示文件系统使用情况，包括文件系统类型(-T)和可读格式(-h)
    "df -i",                                        # 检查inode使用情况
    "mount",                                        # 显示当前挂载的文件系统
    "sudo lshw -short",                             # 显示系统硬件概要信息
    "cat /proc/cpuinfo | grep 'model name' | uniq", # 显示CPU型号信息（去除重复）
    "cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable'", # 显示内存总量和可用量
    "free -m",                                      # 显示系统内存使用情况（MB为单位）
    
    # 网络信息
    "ip addr",                                      # 显示所有网络接口信息
    "ss -tunlp",                                    # 显示所有TCP(-t)和UDP(-u)监听(-l)端口，显示进程(-p)和数字端口(-n)
    "route -n",                                     # 显示内核路由表（以数字形式）
    "netstat -s | head -40",                        # 显示网络统计信息（仅显示前40行重要信息）
    "cat /etc/resolv.conf",                         # 显示系统DNS解析配置
    "sudo cat /etc/hosts.allow /etc/hosts.deny 2>/dev/null",    # 检查TCP Wrapper配置
    "ping -c 3 8.8.8.8",                            # 测试网络连通性（ping谷歌DNS服务器3次）
    
    # 进程与性能
    "ps aux --sort=-%cpu | head -10",               # 显示CPU占用率最高的10个进程
    "ps aux --sort=-%mem | head -10",               # 显示内存占用率最高的10个进程
    "top -bc -n 1 -o %CPU | head -20",              # 显示CPU使用率最高的进程（批处理模式，只运行一次）
    "vmstat 1 3",                                   # 每隔1秒报告系统内存、进程、CPU等统计信息，共3次
    "mpstat -P ALL 1 2",                            # 显示所有CPU核心的详细统计信息，每秒一次，共2次
    "iostat -x 2 2",                                # 显示详细的IO统计信息，每2秒一次，共2次
    "cat /proc/loadavg",                            # 显示系统平均负载
    "nvidia-smi",                                   # 显示NVIDIA GPU状态信息
    
    # 用户与安全信息
    "who",                                          # 显示当前登录的用户
    "last | head -20",                              # 显示最近20条登录记录
    "sudo lastb | head -10",                        # 查看最近10条失败的登录尝试
    "cat /etc/passwd",                              # 显示系统用户账户信息
    "ls -la --time-style=full-iso /etc/passwd /etc/shadow /etc/group",  # 显示用户和组文件的详细时间信息
    "awk -F: '{print $1, $3, $4, $6}' /etc/passwd | sort -n -k2",  # 按照UID排序显示用户列表
    "cat /etc/sudoers 2>/dev/null && ls -l /etc/sudoers.d/ 2>/dev/null",  # 显示sudo权限配置
    "sudo ausearch -m USER_AUTH -m USER_ACCT -m ADD_USER -ts today 2>/dev/null || sudo journalctl _COMM=useradd _COMM=adduser -n 10 2>/dev/null",  # 检查用户添加和认证
    
    # 系统安全性检查
    "sudo find / -perm -4000 -ls 2>/dev/null | head -20",      # 查找具有SUID权限的文件（仅显示前20个）
    "sudo grep -v '^#' /etc/ssh/sshd_config | grep -v '^$'",  # 只显示SSH有效配置行
    "ls -la /root/.ssh/ 2>/dev/null",                           # 检查root的SSH密钥文件
    "sudo find /home -name 'authorized_keys' -o -name 'id_rsa*' 2>/dev/null | head -10",  # 查找所有用户SSH密钥
    "sudo iptables -nvL || sudo firewall-cmd --list-all",     # 检查防火墙规则（二选一）
    
    # 服务与计划任务
    "systemctl list-units --state=running --type=service --no-pager", # 显示正在运行的系统服务单元
    "systemctl list-units --failed --no-pager",            # 列出所有启动失败的服务单元
    "crontab -l 2>/dev/null && ls -l /etc/cron.*",         # 显示计划任务和系统cron目录
    "sudo ls -la /etc/cron.d/ /etc/crontab /var/spool/cron/ 2>/dev/null", # 查看所有crontab文件
    
    # 系统日志分析
    "sudo journalctl -p 3 -n 30 --no-pager 2>/dev/null",   # 查看最近30条错误级别的系统日志
    "sudo dmesg | tail -n 20",                      # 显示最近20条内核缓冲区信息
    "sudo grep -Ei 'error|fail|critical' /var/log/syslog 2>/dev/null || sudo grep -Ei 'error|fail|critical' /var/log/messages 2>/dev/null | tail -20",  # 查找系统日志中的错误
    "sudo find /var/log -type f -size +100M -exec du -h {} \\; 2>/dev/null | sort -rh",  # 查找大于100MB的日志文件
    
    # 存储与文件系统
    "sudo fdisk -l 2>/dev/null || lsblk -f",        # 磁盘分区信息
    "cat /etc/fstab",                               # 显示系统启动时自动挂载的文件系统配置
    # "sudo du -sh /* 2>/dev/null | sort -rh | head -10", # 显示根目录下占用空间最大的10个目录
    
    # 系统限制与配置
    "ulimit -a",                                    # 显示当前用户的资源限制
    "cat /etc/security/limits.conf | grep -v '^#' | grep -v '^$'", # 显示系统资源限制配置（非注释行）
    "sudo sysctl -a 2>/dev/null | grep -E 'vm.swappiness|fs.file-max|net.ipv4.tcp_fin_timeout|net.core.somaxconn'", # 显示关键内核参数
    
    # 容器与云原生
    "sudo docker ps -a 2>/dev/null",                # 显示所有Docker容器
    "kubectl get pods --all-namespaces 2>/dev/null",# 显示所有命名空间中的Kubernetes Pod
    "kubectl get nodes 2>/dev/null",                # 显示Kubernetes集群中的所有节点
    
    # 时间同步
    "date && timedatectl"                           # 显示系统日期、时间和NTP同步状态
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
   - 安全漏洞（弱密码、权限问题、SSH配置、异常用户账户）
   - 性能瓶颈（CPU/内存使用率、IO等待、网络拥塞）
   - 配置错误（服务冲突、失效策略、资源限制）
   - 日志审计（错误日志、内核日志、安全事件）
   - 可疑进程（异常CPU/内存占用、可疑网络连接）

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
  <title>服务器健康检查报告（{{ip}}）</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; }}
    h2 {{ color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
    h3 {{ color: #34495e; }}
    table {{ border-collapse: collapse; width: 80%; margin: 20px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #f8f9fa; }}
    .critical {{ color: red; font-weight: bold; }}
    .warning {{ color: orange; font-weight: bold; }}
    .success {{ color: green; }}
    .section {{ margin-bottom: 30px; }}
    .code {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-family: monospace; overflow-x: auto; }}
    .summary {{ background-color: #eaf2f8; padding: 15px; border-left: 5px solid #3498db; margin: 20px 0; }}
  </style>
</head>
<body>
  <div class="section">
    <h1>服务器健康检查报告（{{ip}}）</h1>
    <div class="summary">
      <p><strong>检查时间：</strong> YYYY-MM-DD HH:MM:SS</p>
      <p><strong>健康状态：</strong> <span class="critical">需要关注</span> / <span class="warning">一般</span> / <span class="success">良好</span></p>
      <p><strong>紧急问题：</strong> X个高危问题，Y个中危问题，Z个低危问题</p>
    </div>

    <div class="section">
      <h2>系统概览</h2>
      <ul>
        <li>操作系统：</li>
        <li>内核版本：</li>
        <li>运行时间：</li>
        <li>最后登录用户：</li>
        <li>系统负载：</li>
        <li>CPU核心数：</li>
        <li>内存总量：</li>
        <li>已使用磁盘空间：</li>
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
      <h3>安全加固</h3>
      <ul>
        <li>SSH安全：
          <ul>
            <li>禁用root远程登录：编辑<code>/etc/ssh/sshd_config</code>，设置<code>PermitRootLogin no</code></li>
            <li>使用密钥认证：设置<code>PasswordAuthentication no</code>，只允许密钥登录</li>
            <li>限制登录IP：使用<code>AllowUsers user@192.168.1.*</code>限制特定用户和IP</li>
            <li>修改默认端口：将默认22端口修改为非标准端口</li>
            <li>启用登录失败限制：使用fail2ban防止暴力破解</li>
          </ul>
        </li>
        <li>账户安全：
          <ul>
            <li>删除不必要账户：<code>userdel -r username</code></li>
            <li>设置密码复杂度：配置PAM模块强制密码策略</li>
            <li>定期轮换密码：配置密码过期策略<code>chage -M 90 username</code></li>
            <li>锁定系统账户：<code>passwd -l username</code>锁定不需要登录的系统账户</li>
          </ul>
        </li>
        <li>网络安全：
          <ul>
            <li>关闭不必要端口：使用防火墙只开放必要服务端口</li>
            <li>配置防火墙规则：设置iptables或firewalld的详细规则</li>
            <li>限制访问来源：设置源IP限制，只允许特定网段访问关键服务</li>
          </ul>
        </li>
        <li>权限控制：
          <ul>
            <li>最小权限原则：清理sudo权限，仅授予所需最小权限</li>
            <li>定期审计sudo权限：检查/etc/sudoers和/etc/sudoers.d/目录</li>
            <li>修复SUID/SGID问题：降低不必要的特权位<code>chmod -s filename</code></li>
          </ul>
        </li>
        <li>安全更新：
          <ul>
            <li>启用自动安全更新：配置unattended-upgrades或yum-cron</li>
            <li>定期检查CVE漏洞：安装漏洞扫描工具</li>
          </ul>
        </li>
      </ul>
      
      <h3>性能优化</h3>
      <ul>
        <li>资源分配：
          <ul>
            <li>优化内存使用：调整swappiness参数<code>sysctl vm.swappiness=10</code></li>
            <li>调整交换空间：设置适当的交换分区大小</li>
            <li>合理分配CPU资源：使用cgroups或nice值调整进程优先级</li>
            <li>优化文件句柄限制：增加系统文件描述符限制<code>ulimit -n 65535</code></li>
          </ul>
        </li>
        <li>存储优化：
          <ul>
            <li>清理大文件：<code>find / -type f -size +100M -exec du -h {} \\;</code></li>
            <li>压缩日志：配置logrotate压缩和轮转日志文件</li>
            <li>配置自动清理：设置定期清理临时文件和旧日志</li>
            <li>监控inode使用：<code>df -i</code>检查inode使用情况</li>
          </ul>
        </li>
        <li>服务精简：
          <ul>
            <li>关闭不必要服务：<code>systemctl disable servicename</code></li>
            <li>减少开机启动项：检查并精简systemd自启动单元</li>
            <li>优化服务配置：根据系统资源调整服务参数</li>
          </ul>
        </li>
        <li>内核调优：
          <ul>
            <li>适配系统负载：通过/etc/sysctl.conf优化内核参数</li>
            <li>优化网络参数：调整TCP缓冲区和并发连接数</li>
            <li>调整IO调度器：选择合适的IO调度策略</li>
          </ul>
        </li>
      </ul>
      
      <h3>可靠性提升</h3>
      <ul>
        <li>监控告警：
          <ul>
            <li>部署监控系统：安装Prometheus、Nagios或Zabbix</li>
            <li>设置关键指标告警：针对CPU、内存、磁盘等资源设置阈值</li>
            <li>配置服务监控：监控关键服务的可用性和性能</li>
          </ul>
        </li>
        <li>备份策略：
          <ul>
            <li>配置定期备份：使用rsync、restic或系统备份工具</li>
            <li>验证数据恢复：定期测试备份的可恢复性</li>
            <li>多层次备份：实施本地+远程备份策略</li>
          </ul>
        </li>
        <li>日志管理：
          <ul>
            <li>集中日志收集：部署ELK或Graylog集中管理日志</li>
            <li>配置日志轮转：优化logrotate策略防止日志占满磁盘</li>
            <li>设置日志审计：启用auditd记录关键操作</li>
          </ul>
        </li>
        <li>系统健康检查：
          <ul>
            <li>配置定期自动巡检：设置cron作业运行系统检查脚本</li>
            <li>硬件监控：监控硬件温度和健康状态</li>
            <li>建立基线：记录系统正常状态作为比较基准</li>
          </ul>
        </li>
      </ul>
      
      <h3>立即执行的命令</h3>
      <div class="code">
        # 在此处提供具体可执行的命令，解决发现的主要问题
      </div>
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
    log_filename = os.path.basename(log_file)
    timestamp = log_filename.split('_')[-1].replace('.log', '')
    
    # 读取日志文件内容
    with open(log_file, 'r', encoding='utf-8') as f:
        data = f.read()

    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        # 使用字符串替换而不是格式化字符串
        formatted_prompt = AI_PROMPT.replace("{{ip}}", ipadd)

        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": data},
            ],
            stream=True,
            temperature=0.3,
            max_tokens=30000
        )

        filename = os.path.join(dir_url, f"{ipadd}_analysis_{timestamp}.html")
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
        # 使用字符串替换而不是格式化
        formatted_prompt = AI_PROMPT.replace("{{ip}}", ipadd)
        
        response = client.generate(
            model='qwen:1.8b',
            system=formatted_prompt,
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
        # 第一步：执行巡检 - 使用ssh_pass作为sudo密码
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
            try:
                analysis_file = AI_V3(log_file, ip, volc_key, base_url, model)
            except Exception as e:
                print(f"Deepseek分析失败: {str(e)}")
                print("尝试使用本地模型分析...")
                analysis_file = local_ollama(raw_data, ip)
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
    ip_address = "47.57.186.97"
    log_file = os.path.join(dir_url, "inspection_47.57.186.97_20250317-171050.log")
    if not os.path.exists(log_file):
        print(f"日志文件不存在: {log_file}")
        return

    with open(log_file, 'r', encoding='utf-8') as f:
        raw_data = f.read()

    try:
        analysis_file = None
        if volc_key:  # 优先使用Deepseek引擎
            print("\n使用Deepseek引擎分析...")
            analysis_file = AI_V3(log_file, ip_address, volc_key, base_url, model)
            if analysis_file:
                print(f"\n分析报告保存至: {analysis_file}")
            else:
                print("Deepseek分析失败，尝试使用本地模型")
                analysis_file = local_ollama(raw_data, ip_address)
        else:
            print("\n没有配置Deepseek API密钥，使用本地模型分析...")
            analysis_file = local_ollama(raw_data, ip_address)
            if analysis_file:
                print(f"\n分析报告保存至: {analysis_file}")
            else:
                print("本地模型分析失败")
    except Exception as e:
        print(f"测试分析异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
    # test_AI()