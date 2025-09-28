#!/bin/bash
# CentOS 交易系统安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 root 用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要 root 权限运行"
        exit 1
    fi
}

# 检查系统版本
check_system() {
    if ! grep -q "CentOS" /etc/os-release; then
        print_warning "此脚本专为 CentOS 设计，其他系统可能不兼容"
    fi
}

# 安装依赖包
install_dependencies() {
    print_info "安装系统依赖包..."
    
    # 更新包管理器
    yum update -y
    
    # 安装 Python 3.8 和相关工具
    yum install -y python38 python3-pip python3-devel
    
    # 安装开发工具
    yum groupinstall -y "Development Tools"
    
    # 安装其他必要包
    yum install -y git wget curl vim
    
    print_success "系统依赖包安装完成"
}

# 创建交易系统用户
create_user() {
    print_info "创建交易系统用户..."
    
    if ! id "trading" &>/dev/null; then
        useradd -r -s /bin/false -d /opt/trading trading
        print_success "用户 'trading' 创建完成"
    else
        print_info "用户 'trading' 已存在"
    fi
}

# 复制项目文件
copy_project_files() {
    print_info "复制项目文件到安装目录..."
    
    # 获取当前脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 复制项目文件到安装目录
    cp -r "$SCRIPT_DIR"/* /opt/trading/
    
    # 排除不需要的文件
    rm -f /opt/trading/install.sh
    
    print_success "项目文件复制完成"
}

# 创建虚拟环境
create_venv() {
    print_info "创建 Python 虚拟环境..."
    
    cd /opt/trading
    
    # 检查是否已存在虚拟环境
    if [ -d "venv" ]; then
        print_warning "虚拟环境已存在，删除旧环境..."
        rm -rf venv
    fi
    
    # 创建虚拟环境
    if python38 -m venv venv; then
        print_success "虚拟环境创建成功"
        
        # 激活虚拟环境并升级 pip
        if source venv/bin/activate && pip install --upgrade pip; then
            print_success "pip 升级完成"
        else
            print_error "pip 升级失败"
            return 1
        fi
    else
        print_error "虚拟环境创建失败"
        return 1
    fi
    
    print_success "虚拟环境创建完成"
}

# 安装 Python 依赖
install_python_deps() {
    print_info "安装 Python 依赖包..."
    
    cd /opt/trading
    
    # 检查虚拟环境是否存在
    if [ ! -d "venv" ]; then
        print_error "虚拟环境不存在，请先创建虚拟环境"
        return 1
    fi
    
    # 激活虚拟环境
    if source venv/bin/activate; then
        # 检查 OpenSSL 版本
        print_info "检查 OpenSSL 版本兼容性..."
        openssl_version=$(python -c "import ssl; print(ssl.OPENSSL_VERSION)" 2>/dev/null)
        if [[ $openssl_version == *"1.0.2"* ]]; then
            print_warning "检测到 OpenSSL 1.0.2，将使用兼容的 urllib3 版本"
            # 先安装兼容的 urllib3 版本
            pip install "urllib3<2.0.0"
        fi
        
        # 安装项目依赖
        if pip install -r requirements.txt; then
            print_success "Python 依赖包安装完成"
        else
            print_error "Python 依赖包安装失败"
            return 1
        fi
    else
        print_error "无法激活虚拟环境"
        return 1
    fi
}

# 配置服务文件
setup_service() {
    print_info "配置 systemd 服务..."
    
    # 检查 systemd 版本
    systemd_version=$(systemctl --version | head -n1 | awk '{print $2}')
    print_info "检测到 systemd 版本: $systemd_version"
    
    # 复制服务文件
    cp trading-system.service /etc/systemd/system/
    
    # 检查服务文件语法
    if systemctl cat trading-system >/dev/null 2>&1; then
        print_success "服务文件语法检查通过"
    else
        print_warning "服务文件语法检查失败，尝试修复..."
        # 移除不兼容的选项
        sed -i '/^ReadWritePaths=/d' /etc/systemd/system/trading-system.service
        sed -i '/^ProtectSystem=/d' /etc/systemd/system/trading-system.service
        print_success "服务文件已修复"
    fi
    
    # 重新加载 systemd
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable trading-system
    
    print_success "服务配置完成"
}

# 设置基础权限
setup_permissions() {
    print_info "设置基础文件权限..."
    
    # 创建应用目录
    mkdir -p /opt/trading
    mkdir -p /opt/trading/logs
    
    # 设置目录权限
    chown -R trading:trading /opt/trading
    chmod -R 755 /opt/trading
    
    # 设置日志目录权限
    chown trading:trading /opt/trading/logs
    chmod 755 /opt/trading/logs
    
    print_success "基础权限设置完成"
}

# 设置虚拟环境权限
setup_venv_permissions() {
    print_info "设置虚拟环境权限..."
    
    if [ -d "/opt/trading/venv" ]; then
        chmod -R 755 /opt/trading/venv
        print_success "虚拟环境权限设置完成"
    else
        print_warning "虚拟环境目录不存在，跳过权限设置"
    fi
}

# 创建配置文件
create_config() {
    print_info "创建配置文件..."
    
    # 创建环境配置文件
    cat > /opt/trading/.env << EOF
# 交易系统环境配置
TRADING_MODE=service
LOG_LEVEL=INFO
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
EOF
    
    chown trading:trading /opt/trading/.env
    chmod 600 /opt/trading/.env
    
    print_warning "请编辑 /opt/trading/.env 文件，设置您的 API 密钥"
    print_success "配置文件创建完成"
}

# 创建管理脚本
create_management_scripts() {
    print_info "创建管理脚本..."
    
    # 启动脚本
    cat > /opt/trading/start.sh << 'EOF'
#!/bin/bash
systemctl start trading-system
systemctl status trading-system
EOF
    
    # 停止脚本
    cat > /opt/trading/stop.sh << 'EOF'
#!/bin/bash
systemctl stop trading-system
systemctl status trading-system
EOF
    
    # 重启脚本
    cat > /opt/trading/restart.sh << 'EOF'
#!/bin/bash
systemctl restart trading-system
systemctl status trading-system
EOF
    
    # 查看日志脚本
    cat > /opt/trading/logs.sh << 'EOF'
#!/bin/bash
journalctl -u trading-system -f
EOF
    
    # 修复权限脚本
    cat > /opt/trading/fix_permissions.sh << 'EOF'
#!/bin/bash
echo "修复交易系统权限..."
cd /opt/trading

# 修复虚拟环境权限
if [ -d "venv" ]; then
    echo "修复虚拟环境权限..."
    chown -R trading:trading venv
    chmod -R 755 venv
    chmod +x venv/bin/activate
    chmod +x venv/bin/python
    chmod +x venv/bin/pip
    echo "虚拟环境权限修复完成"
else
    echo "虚拟环境不存在"
fi

# 修复项目文件权限
echo "修复项目文件权限..."
chown -R trading:trading /opt/trading
chmod -R 755 /opt/trading
chmod 755 /opt/trading/logs

echo "权限修复完成"
EOF
    
    # 修复 urllib3 兼容性脚本
    cat > /opt/trading/fix_urllib3.sh << 'EOF'
#!/bin/bash
echo "修复 urllib3 兼容性问题..."
cd /opt/trading

if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
    
    echo "检查 OpenSSL 版本..."
    openssl_version=$(python -c "import ssl; print(ssl.OPENSSL_VERSION)" 2>/dev/null)
    echo "OpenSSL 版本: $openssl_version"
    
    if [[ $openssl_version == *"1.0.2"* ]]; then
        echo "检测到 OpenSSL 1.0.2，安装兼容的 urllib3 版本..."
        pip uninstall -y urllib3
        pip install "urllib3<2.0.0"
        echo "urllib3 兼容性修复完成"
    else
        echo "OpenSSL 版本兼容，无需修复"
    fi
else
    echo "虚拟环境不存在"
fi
EOF
    
    # 修复服务文件脚本
    cat > /opt/trading/fix_service.sh << 'EOF'
#!/bin/bash
echo "修复 systemd 服务文件兼容性问题..."

# 检查 systemd 版本
systemd_version=$(systemctl --version | head -n1 | awk '{print $2}')
echo "检测到 systemd 版本: $systemd_version"

# 备份原服务文件
if [ -f "/etc/systemd/system/trading-system.service" ]; then
    cp /etc/systemd/system/trading-system.service /etc/systemd/system/trading-system.service.backup
    echo "已备份原服务文件"
fi

# 移除不兼容的选项
sed -i '/^ReadWritePaths=/d' /etc/systemd/system/trading-system.service
sed -i '/^ProtectSystem=/d' /etc/systemd/system/trading-system.service

# 重新加载 systemd
systemctl daemon-reload

# 检查服务文件语法
if systemctl cat trading-system >/dev/null 2>&1; then
    echo "服务文件修复成功"
    systemctl status trading-system --no-pager
else
    echo "服务文件修复失败，请检查配置"
fi
EOF
    
    # 设置执行权限
    chmod +x /opt/trading/*.sh
    chown trading:trading /opt/trading/*.sh
    
    print_success "管理脚本创建完成"
}

# 测试安装
test_installation() {
    print_info "测试安装..."
    
    # 测试虚拟环境
    cd /opt/trading
    if [ -d "venv" ] && source venv/bin/activate && python --version; then
        print_success "虚拟环境测试通过"
    else
        print_error "虚拟环境测试失败"
        print_info "尝试修复虚拟环境..."
        fix_venv_permissions
        return 1
    fi
    
    # 测试服务文件
    if systemctl is-enabled trading-system >/dev/null 2>&1; then
        print_success "服务配置测试通过"
    else
        print_error "服务配置测试失败"
        return 1
    fi
    
    print_success "安装测试完成"
}

# 修复虚拟环境权限
fix_venv_permissions() {
    print_info "修复虚拟环境权限..."
    
    cd /opt/trading
    
    if [ -d "venv" ]; then
        # 重新设置虚拟环境权限
        chown -R trading:trading venv
        chmod -R 755 venv
        
        # 确保激活脚本可执行
        chmod +x venv/bin/activate
        chmod +x venv/bin/python
        chmod +x venv/bin/pip
        
        print_success "虚拟环境权限修复完成"
    else
        print_error "虚拟环境目录不存在，无法修复"
        return 1
    fi
}

# 显示使用说明
show_usage() {
    echo
    print_success "交易系统安装完成！"
    echo
    echo "使用说明："
    echo "  启动服务: systemctl start trading-system"
    echo "  停止服务: systemctl stop trading-system"
    echo "  重启服务: systemctl restart trading-system"
    echo "  查看状态: systemctl status trading-system"
    echo "  查看日志: journalctl -u trading-system -f"
    echo
    echo "或者使用管理脚本："
    echo "  启动: /opt/trading/start.sh"
    echo "  停止: /opt/trading/stop.sh"
    echo "  重启: /opt/trading/restart.sh"
    echo "  日志: /opt/trading/logs.sh"
    echo "  修复权限: /opt/trading/fix_permissions.sh"
    echo "  修复urllib3: /opt/trading/fix_urllib3.sh"
    echo "  修复服务: /opt/trading/fix_service.sh"
    echo
    print_warning "重要提醒："
    echo "1. 请编辑 /opt/trading/.env 文件，设置您的 API 密钥"
    echo "2. 请检查 /opt/trading/config.py 文件，确认交易参数"
    echo "3. 建议先在测试环境验证系统功能"
    echo "4. 虚拟环境路径: /opt/trading/venv"
    echo
}

# 主函数
main() {
    print_info "开始安装交易系统..."
    
    check_root
    check_system
    install_dependencies
    create_user
    setup_permissions
    copy_project_files
    create_venv
    setup_venv_permissions
    install_python_deps
    create_config
    setup_service
    create_management_scripts
    test_installation
    show_usage
    
    print_success "安装完成！"
}

# 处理命令行参数
case "${1:-}" in
    --fix-permissions)
        print_info "运行权限修复..."
        fix_venv_permissions
        print_success "权限修复完成"
        exit 0
        ;;
    --fix-urllib3)
        print_info "运行 urllib3 兼容性修复..."
        cd /opt/trading
        if [ -d "venv" ]; then
            source venv/bin/activate
            openssl_version=$(python -c "import ssl; print(ssl.OPENSSL_VERSION)" 2>/dev/null)
            if [[ $openssl_version == *"1.0.2"* ]]; then
                pip uninstall -y urllib3
                pip install "urllib3<2.0.0"
                print_success "urllib3 兼容性修复完成"
            else
                print_info "OpenSSL 版本兼容，无需修复"
            fi
        else
            print_error "虚拟环境不存在"
        fi
        exit 0
        ;;
    --fix-service)
        print_info "运行服务文件兼容性修复..."
        systemd_version=$(systemctl --version | head -n1 | awk '{print $2}')
        print_info "检测到 systemd 版本: $systemd_version"
        
        if [ -f "/etc/systemd/system/trading-system.service" ]; then
            cp /etc/systemd/system/trading-system.service /etc/systemd/system/trading-system.service.backup
            sed -i '/^ReadWritePaths=/d' /etc/systemd/system/trading-system.service
            sed -i '/^ProtectSystem=/d' /etc/systemd/system/trading-system.service
            systemctl daemon-reload
            
            if systemctl cat trading-system >/dev/null 2>&1; then
                print_success "服务文件修复完成"
            else
                print_error "服务文件修复失败"
            fi
        else
            print_error "服务文件不存在"
        fi
        exit 0
        ;;
    --help|-h)
        echo "用法: $0 [选项]"
        echo "选项:"
        echo "  --fix-permissions    修复虚拟环境和文件权限"
        echo "  --fix-urllib3        修复 urllib3 兼容性问题"
        echo "  --fix-service        修复 systemd 服务文件兼容性"
        echo "  --help, -h          显示此帮助信息"
        echo
        echo "示例:"
        echo "  $0                  完整安装"
        echo "  $0 --fix-permissions 仅修复权限"
        echo "  $0 --fix-urllib3    仅修复 urllib3 兼容性"
        echo "  $0 --fix-service    仅修复服务文件兼容性"
        exit 0
        ;;
    "")
        # 无参数，运行完整安装
        ;;
    *)
        echo "未知选项: $1"
        echo "使用 --help 查看帮助信息"
        exit 1
        ;;
esac

# 运行主函数
main "$@" 