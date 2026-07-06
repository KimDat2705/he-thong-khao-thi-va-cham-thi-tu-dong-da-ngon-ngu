@echo off
chcp 65001 >nul
title Tao bo de mau de nghiem thu (nha may sinh cau B1)
cd /d "%~dp0backend"

echo ============================================================
echo   TAO BO DE MAU DE NGHIEM THU
echo   (Bam dup file nay - khong can go lenh)
echo ------------------------------------------------------------
echo   - Neu co GEMINI_API_KEY trong backend\.env : sinh THAT (chat luong that).
echo   - Neu chua co key : chay MOCK (chi de xem cau truc, noi dung gia).
echo ============================================================
echo.

if exist venv\Scripts\python.exe (
  set "PY=venv\Scripts\python.exe"
) else (
  set "PY=python"
)

set PYTHONIOENCODING=utf-8
"%PY%" scripts\make_bank_expansion.py ^
  --bank-raw tests\fixtures\factory_sample\bank_raw.json ^
  --pool-speak tests\fixtures\factory_sample\pool_speak.json ^
  --pool-lis tests\fixtures\factory_sample\pool_lis.json ^
  --per-seed 1 --n-target 1 --verify ^
  --out "%~dp0san_pham_de_mau"

echo.
echo ============================================================
echo   XONG! Cac file de + bao cao nam trong thu muc:
echo   %~dp0san_pham_de_mau
echo   Dang mo thu muc do...
echo ============================================================
start "" "%~dp0san_pham_de_mau"
echo.
pause
