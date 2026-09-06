"""端口转发：8080 → 8000
让微信小程序访问 8080 端口时自动转到后端 8000。
用法：python scripts/port_forward.py（后台运行，Ctrl+C 停止）
"""
import socket
import threading
import sys


def forward(src, dst):
    """把 src socket 的数据转发到 dst socket"""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def handle(client, client_addr):
    """处理一个客户端连接：连接后端 8000，双向转发"""
    try:
    # 连接到本机后端 8000
        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend.settimeout(5)
        backend.connect(("127.0.0.1", 8000))
        backend.settimeout(None)
        # 双向转发
        t1 = threading.Thread(target=forward, args=(client, backend), daemon=True)
        t2 = threading.Thread(target=forward, args=(backend, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
    except Exception as exc:
        print(f"[WARN] 转发失败 {client_addr}: {exc}")
        try:
            client.close()
        except Exception:
            pass


def main():
    listen_port = 8080
    target_host = "127.0.0.1"
    target_port = 8000

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", listen_port))
    server.listen(50)
    print(f"[OK] 端口转发已启动：0.0.0.0:{listen_port} → {target_host}:{target_port}")
    print(f"     微信小程序访问 8080 会自动转到后端 8000")
    print(f"     按 Ctrl+C 停止")
    try:
        while True:
            client, addr = server.accept()
            t = threading.Thread(target=handle, args=(client, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[OK] 端口转发已停止")
    finally:
        server.close()


if __name__ == "__main__":
    main()
