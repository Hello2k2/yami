# -*- coding: utf-8 -*-
# yami/dlna_service.py

import asyncio
import socket
import threading
import logging
import uuid
import platform
from async_upnp_client.ssdp_server import SsdpServer
from async_upnp_client.aiohttp_server import AiohttpServer
from aiohttp import web # Cần web từ aiohttp để tạo Response

# --- Cấu hình Logging ---
log = logging.getLogger("DLNAService")
# Đặt logging level cao hơn để thấy thông tin debug từ async_upnp_client nếu cần
# logging.getLogger("async_upnp_client").setLevel(logging.DEBUG)

# --- Thông tin cơ bản về DLNA Server ---
# Tạo một UUID cố định cho server hoặc tạo mới mỗi lần (nên dùng cố định)
# Bạn có thể thay đổi phần cuối này để đảm bảo là duy nhất
SERVER_UDN = f"uuid:yami-server-{uuid.uuid4()}"
FRIENDLY_NAME = "Yami Media Server"
MANUFACTURER = "Yami User"
MODEL_NAME = "Yami DLNA/UPnP Server"
# Đây là loại thiết bị chuẩn cho Media Server
DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaServer:1"
# Các dịch vụ mà server này sẽ cung cấp (Tạm thời chỉ có CDS và CMS cơ bản)
SERVICE_CDS_TYPE = "urn:schemas-upnp-org:service:ContentDirectory:1"
SERVICE_CMS_TYPE = "urn:schemas-upnp-org:service:ConnectionManager:1"
SERVICE_CDS_ID = "urn:upnp-org:serviceId:ContentDirectory"
SERVICE_CMS_ID = "urn:upnp-org:serviceId:ConnectionManager"


# --- Biến toàn cục cho luồng và loop asyncio ---
_dlna_thread = None
_async_loop = None
_shutdown_event = None # Event để báo hiệu dừng cho coroutine

# === Hàm tạo nội dung XML mô tả thiết bị ===
def _generate_device_xml(ip_address, http_port):
    """Tạo nội dung XML cho file /device.xml"""
    # Các URL này client sẽ dùng để lấy mô tả chi tiết về dịch vụ
    cds_scpd_url = f"http://{ip_address}:{http_port}/cds.xml"
    cds_control_url = f"http://{ip_address}:{http_port}/cds/control" # Client gửi lệnh duyệt tới đây
    cds_event_sub_url = f"http://{ip_address}:{http_port}/cds/event" # Client đăng ký nhận sự kiện thay đổi

    cms_scpd_url = f"http://{ip_address}:{http_port}/cms.xml"
    cms_control_url = f"http://{ip_address}:{http_port}/cms/control"
    cms_event_sub_url = f"http://{ip_address}:{http_port}/cms/event"

    # Lấy thông tin hệ thống cơ bản
    system_info = f"{platform.system()} {platform.release()}"
    model_number = platform.python_version()

    # Tạo chuỗi XML (cần rất cẩn thận với namespace và cấu trúc)
    # Đây là cấu trúc rất cơ bản, có thể cần thêm các trường khác
    xml_content = f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <device>
        <deviceType>{DEVICE_TYPE}</deviceType>
        <friendlyName>{FRIENDLY_NAME}</friendlyName>
        <manufacturer>{MANUFACTURER}</manufacturer>
        <modelDescription>Yami Media Server based on Python</modelDescription>
        <modelName>{MODEL_NAME}</modelName>
        <modelNumber>{model_number}</modelNumber>
        <UDN>{SERVER_UDN}</UDN>
        <presentationURL>http://{ip_address}:{http_port}/</presentationURL> ```
        <serviceList>
            <service>
                <serviceType>{SERVICE_CDS_TYPE}</serviceType>
                <serviceId>{SERVICE_CDS_ID}</serviceId>
                <SCPDURL>{cds_scpd_url}</SCPDURL>
                <controlURL>{cds_control_url}</controlURL>
                <eventSubURL>{cds_event_sub_url}</eventSubURL>
            </service>

            <service>
                <serviceType>{SERVICE_CMS_TYPE}</serviceType>
                <serviceId>{SERVICE_CMS_ID}</serviceId>
                <SCPDURL>{cms_scpd_url}</SCPDURL>
                <controlURL>{cms_control_url}</controlURL>
                <eventSubURL>{cms_event_sub_url}</eventSubURL>
            </service>
            
            <service>
                <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
                <serviceId>urn:upnp-org:serviceId:AVTransport</serviceId>
                <SCPDURL>/avt.xml</SCPDURL>
                <controlURL>/avt/control</controlURL>
                <eventSubURL>/avt/event</eventSubURL>
            </service>
           
        </serviceList>
        
    </device>
</root>
"""
    return xml_content.strip()

# === Hàm tạo nội dung XML mô tả dịch vụ CDS (Tạm thời rất đơn giản) ===
def _generate_cds_xml():
    """Tạo XML mô tả dịch vụ Content Directory (SCPD)."""
    # Cần định nghĩa các action (Browse, Search, GetSortCapabilities...)
    # và các state variable (SystemUpdateID, ContainerUpdateIDs...)
    # Đây là phần phức tạp, tạm thời trả về cấu trúc rỗng hoặc rất cơ bản
    xml_content = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <actionList>
        {/* TODO: Định nghĩa Action Browse ở đây */}
        {/* Ví dụ:
        <action>
            <name>Browse</name>
            <argumentList>
                <argument>...</argument>
            </argumentList>
        </action>
         */}
    </actionList>
    <serviceStateTable>
        {/* TODO: Định nghĩa các State Variable ở đây */}
        {/* Ví dụ: <stateVariable sendEvents="yes"> <name>SystemUpdateID</name> ... </stateVariable> */}
    </serviceStateTable>
</scpd>
"""
    return xml_content.strip()

# === Hàm tạo nội dung XML mô tả dịch vụ CMS (Tạm thời rất đơn giản) ===
def _generate_cms_xml():
    """Tạo XML mô tả dịch vụ Connection Manager (SCPD)."""
    # Chủ yếu định nghĩa action GetProtocolInfo
    xml_content = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <actionList>
       {/* TODO: Định nghĩa Action GetProtocolInfo */}
    </actionList>
    <serviceStateTable>
       {/* TODO: Định nghĩa State Variable SourceProtocolInfo, SinkProtocolInfo... */}
    </serviceStateTable>
</scpd>
"""
    return xml_content.strip()


# === Hàm chính chạy các dịch vụ DLNA bất đồng bộ ===
async def async_start_dlna_core_services(yami_ip, http_desc_port):
    """
    Khởi chạy SSDP server và Aiohttp server cho description files.
    Chạy trong asyncio event loop.
    """
    global _shutdown_event
    loop = asyncio.get_running_loop()
    _shutdown_event = asyncio.Event() # Event để dừng coroutine này

    ssdp_server = None
    aiohttp_server = None
    log.info("Starting DLNA core services...")

    # --- 1. Khởi động Aiohttp Server (Phục vụ file XML mô tả) ---
    # Chạy trên port riêng (khác port Flask phục vụ media file)
    try:
        log.info(f"Attempting to start Aiohttp server for descriptions on {yami_ip}:{http_desc_port}")

        # Hàm xử lý request cho /device.xml
        async def handle_device_xml(request):
            log.debug(f"Received request for /device.xml from {request.remote}")
            content = _generate_device_xml(yami_ip, http_desc_port)
            return web.Response(text=content, content_type="text/xml", charset="utf-8")

        # Hàm xử lý request cho /cds.xml (mô tả dịch vụ CDS)
        async def handle_cds_xml(request):
            log.debug(f"Received request for /cds.xml from {request.remote}")
            content = _generate_cds_xml()
            return web.Response(text=content, content_type="text/xml", charset="utf-8")

        # Hàm xử lý request cho /cms.xml (mô tả dịch vụ CMS)
        async def handle_cms_xml(request):
            log.debug(f"Received request for /cms.xml from {request.remote}")
            content = _generate_cms_xml()
            return web.Response(text=content, content_type="text/xml", charset="utf-8")

        # --- TODO: Thêm các hàm xử lý cho controlURL của CDS và CMS ---
        # Ví dụ: async def handle_cds_control(request): ...
        # Hàm này sẽ nhận SOAP request từ client (Browse, Search...)
        # và phải trả về SOAP response chứa DIDL-Lite XML. Đây là phần phức tạp nhất.
        async def handle_cds_control(request):
             log.warning(f"Received CDS control request from {request.remote} - NOT IMPLEMENTED YET")
             # Đọc SOAP request body
             # Phân tích action (Browse, Search...) và các tham số
             # Lấy danh sách file/thư mục từ Yami instance (CẦN TRUY CẬP YAMI INSTANCE)
             # Tạo DIDL-Lite XML response
             # Trả về SOAP response
             body = await request.text()
             log.debug(f"CDS Request Body:\n{body}")
             # Trả về lỗi tạm thời
             soap_error = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
   <s:Body>
      <s:Fault>
         <faultcode>s:Client</faultcode>
         <faultstring>UPnPError</faultstring>
         <detail>
            <UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
               <errorCode>501</errorCode>
               <errorDescription>Action Failed (Not Implemented)</errorDescription>
            </UPnPError>
         </detail>
      </s:Fault>
   </s:Body>
</s:Envelope>"""
             return web.Response(text=soap_error, status=500, content_type='text/xml; charset="utf-8"', headers={'EXT': ''})


        # Tạo và khởi động Aiohttp server
        aiohttp_server = AiohttpServer(
            source_ip=yami_ip,
            http_port=http_desc_port,
            loop=loop,
        )
        # Thêm các route
        aiohttp_server.router.add_get("/device.xml", handle_device_xml)
        aiohttp_server.router.add_get("/cds.xml", handle_cds_xml)
        aiohttp_server.router.add_get("/cms.xml", handle_cms_xml)
        # Route cho control point của CDS (thường là POST)
        aiohttp_server.router.add_post("/cds/control", handle_cds_control)
        # Thêm các route khác cho CMS control/event, CDS event nếu cần

        await aiohttp_server.start()
        log.info(f"Aiohttp server for DLNA descriptions started on port {aiohttp_server.http_port}")
        print(f"Aiohttp server for DLNA descriptions started on port {aiohttp_server.http_port}")

    except Exception as e:
        log.exception(f"Failed to start Aiohttp server: {e}")
        print(f"!!!!!!!! ERROR starting Aiohttp server: {e} !!!!!!!!")
        _shutdown_event.set() # Báo hiệu dừng nếu server lỗi

    # --- 2. Khởi động SSDP Server (Quảng bá) ---
    if not _shutdown_event.is_set(): # Chỉ chạy nếu aiohttp server ok
        try:
            location = f"http://{yami_ip}:{http_desc_port}/device.xml"
            server_id = f"Yami/{platform.python_version()} UPnP/1.0 DLNA/1.5" # Thông tin server

            log.info(f"Attempting to start SSDP server, advertising location: {location}")
            ssdp_server = SsdpServer(
                source_ip=yami_ip,
                # source_port=ssdp_port, # Thường không cần set, tự động chọn
                http_port=http_desc_port,
                server_usn=f"{SERVER_UDN}::{DEVICE_TYPE}", # USN cho device
                server_udn=SERVER_UDN,
                server_type=DEVICE_TYPE,
                server_location=location,
                server_info=server_id,
                loop=loop,
            )
            await ssdp_server.start()

            # Bắt đầu quảng bá NOTIFY định kỳ cho các loại khác nhau
            # Client thường tìm kiếm rootdevice, device type, và các service type
            await ssdp_server.async_start_notify(SERVER_UDN, "upnp:rootdevice", location, server_id)
            await ssdp_server.async_start_notify(SERVER_UDN, SERVER_UDN, location, server_id) # Thông báo cả UDN
            await ssdp_server.async_start_notify(SERVER_UDN, DEVICE_TYPE, location, server_id)
            await ssdp_server.async_start_notify(SERVER_UDN, SERVICE_CDS_TYPE, location, server_id) # Quảng bá cả service
            await ssdp_server.async_start_notify(SERVER_UDN, SERVICE_CMS_TYPE, location, server_id)

            log.info(f"SSDP Server started and notifying on {yami_ip}")
            print(f"SSDP Server started and notifying on {yami_ip}")

        except Exception as e:
            log.exception(f"Failed to start SSDP server: {e}")
            print(f"!!!!!!!! ERROR starting SSDP server: {e} !!!!!!!!")
            _shutdown_event.set() # Báo hiệu dừng

    # --- Giữ cho các dịch vụ chạy ---
    if not _shutdown_event.is_set():
        log.info("DLNA core services running. Waiting for shutdown signal...")
        print("DLNA core services running. Waiting for shutdown signal...")
        await _shutdown_event.wait() # Chờ cho đến khi event được set
        log.info("Shutdown signal received.")
        print("Shutdown signal received.")

    # --- Dọn dẹp khi dừng ---
    log.info("Stopping DLNA services...")
    print("Stopping DLNA services...")
    if ssdp_server:
        try:
            await ssdp_server.stop()
            log.info("SSDP Server stopped.")
            print("SSDP Server stopped.")
        except Exception as e:
            log.exception(f"Error stopping SSDP server: {e}")
    if aiohttp_server:
        try:
            await aiohttp_server.stop()
            log.info("Aiohttp server stopped.")
            print("Aiohttp server stopped.")
        except Exception as e:
            log.exception(f"Error stopping Aiohttp server: {e}")

    log.info("DLNA core services stopped.")
    print("DLNA core services stopped.")


# === Hàm chạy asyncio loop trong thread ===
def run_asyncio_loop_in_thread(loop):
    """Chạy event loop của asyncio trong một luồng riêng."""
    asyncio.set_event_loop(loop)
    log.info(f"Asyncio event loop {id(loop)} starting in thread {threading.get_ident()}")
    try:
        loop.run_forever()
    finally:
        # Dọn dẹp khi loop dừng hẳn
        log.info("Asyncio event loop shutting down...")
        try:
            # Hủy các task còn lại
            tasks = asyncio.all_tasks(loop=loop)
            for task in tasks:
                task.cancel()
            # Chạy thêm một lần để xử lý việc hủy task
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as e:
            log.exception(f"Error during asyncio loop cleanup: {e}")
        finally:
             loop.close()
             log.info(f"Asyncio event loop {id(loop)} closed.")
             print("Asyncio event loop closed.")


# === Hàm khởi động luồng DLNA ===
def start_dlna_service_thread(yami_app_ip, http_desc_port):
    """Khởi động luồng chạy DLNA services (SSDP và Aiohttp mô tả)."""
    global _dlna_thread, _async_loop
    if _dlna_thread and _dlna_thread.is_alive():
        log.warning("DLNA service thread already running.")
        print("DLNA service thread already running.")
        return True # Báo thành công giả vì nó đã chạy

    log.info("Attempting to start DLNA service thread...")
    try:
        # Tạo event loop mới cho luồng này
        _async_loop = asyncio.new_event_loop()
        _dlna_thread = threading.Thread(
            target=run_asyncio_loop_in_thread,
            args=(_async_loop,),
            name="DLNAServiceThread", # Đặt tên cho luồng
            daemon=True
        )
        _dlna_thread.start()

        # Đợi một chút để đảm bảo luồng và loop đã thực sự chạy
        # time.sleep(0.1) # Có thể không cần thiết

        # Lên lịch chạy coroutine chính trên event loop đó từ luồng này
        future = asyncio.run_coroutine_threadsafe(
            async_start_dlna_core_services(yami_app_ip, http_desc_port),
            _async_loop
        )
        # Không cần đợi future ở đây, cứ để nó chạy ngầm
        log.info("DLNA service thread started and coroutine scheduled.")
        print("DLNA service thread started.")
        return True
    except Exception as e:
        log.exception(f"Failed to start DLNA thread: {e}")
        print(f"!!!!!!!! ERROR starting DLNA thread: {e} !!!!!!!!")
        # Dọn dẹp nếu lỗi khởi động
        if _async_loop and _async_loop.is_running():
             _async_loop.call_soon_threadsafe(_async_loop.stop)
        _dlna_thread = None
        _async_loop = None
        return False


# === Hàm dừng luồng DLNA ===
def stop_dlna_service_thread():
    """Dừng các dịch vụ DLNA và luồng asyncio một cách an toàn."""
    global _dlna_thread, _async_loop, _shutdown_event
    if not _async_loop or not _async_loop.is_running():
        log.info("DLNA thread/loop not running.")
        print("DLNA thread/loop not running.")
        return

    log.info("Requesting DLNA services shutdown...")
    print("Requesting DLNA services shutdown...")
    try:
        # Gửi tín hiệu dừng cho coroutine chính
        if _shutdown_event and not _shutdown_event.is_set():
            # Gọi _shutdown_event.set() một cách an toàn từ luồng khác
             _async_loop.call_soon_threadsafe(_shutdown_event.set)
             log.info("Shutdown event set for DLNA coroutine.")
             print("Shutdown event set for DLNA coroutine.")
        else:
             log.warning("Shutdown event not available or already set.")
             # Vẫn cố gắng dừng loop trực tiếp

        # Yêu cầu event loop dừng lại
        if _async_loop.is_running():
            _async_loop.call_soon_threadsafe(_async_loop.stop)
            log.info("Stop requested for asyncio loop.")
            print("Stop requested for asyncio loop.")

        # Chờ luồng kết thúc (có timeout)
        if _dlna_thread and _dlna_thread.is_alive():
            log.info("Waiting for DLNA thread to join...")
            print("Waiting for DLNA thread to join...")
            _dlna_thread.join(timeout=5) # Chờ tối đa 5 giây
            if _dlna_thread.is_alive():
                log.warning("DLNA thread did not join cleanly after stop request.")
                print("DLNA thread did not join cleanly.")
            else:
                log.info("DLNA thread joined successfully.")
                print("DLNA thread joined successfully.")

    except Exception as e:
        log.exception(f"Error stopping DLNA thread: {e}")
        print(f"!!!!!!!! ERROR stopping DLNA thread: {e} !!!!!!!!")
    finally:
        # Reset biến toàn cục
        _dlna_thread = None
        _async_loop = None
        _shutdown_event = None
        log.info("DLNA service thread and loop variables reset.")
        print("DLNA service thread and loop variables reset.")


# --- Có thể thêm code chạy thử nghiệm ở đây nếu muốn ---
if __name__ == '__main__':
     print("Running dlna_service.py directly for SSDP testing...")
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

     # Lấy IP LAN để test
     ip = '0.0.0.0' # Hoặc gọi hàm lấy IP thực tế
     port = 8081 # Port riêng cho description XML

     print(f"Starting DLNA services (SSDP+Aiohttp desc) on IP {ip}, Port {port}")
     started = start_dlna_service_thread(ip, port)

     if started:
          print("\nDLNA services started in background thread.")
          print("Use a DLNA client (like VLC's UPnP browser, BubbleUPnP) on another device on the same network.")
          print("You should see 'Yami Media Server'.")
          print("Browse content will likely fail as CDS is not fully implemented yet.")
          input("Press Enter to stop the DLNA services...\n")
     else:
          print("\nFailed to start DLNA services.")

     stop_dlna_service_thread()
     print("Test finished.")