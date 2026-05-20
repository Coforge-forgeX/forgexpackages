def register_sharepoint_tools(mcp, sp_service):
    @mcp.tool()
    async def list_sharepoint_files(folder_path: str) -> dict:
        try:
            data = sp_service.list_files(folder_path)
            return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def fetch_sharepoint_file(file_id: str) -> dict:
        try:
            content = sp_service.download_file(file_id)
            return {"status": "success", "size": len(content) if content else 0}
        except Exception as e:
            return {"status": "error", "message": str(e)}
