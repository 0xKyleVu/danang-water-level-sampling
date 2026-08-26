@echo off
REM Wrapper cho Windows Task Scheduler. Dung khi GitHub Actions bi chan IP
REM (Azure datacenter IP range bi WAF cua muangap-api chan).
REM Van day du lieu ve cung 1 repo GitHub cong khai, chi doi noi chay.
cd /d "%~dp0"
echo. >> run_log.txt
echo ===== %date% %time% ===== >> run_log.txt

python collect_water_level.py >> run_log.txt 2>&1

git add water_level_samples.csv >> run_log.txt 2>&1
git diff --staged --quiet
if %errorlevel% equ 0 (
    echo Khong co du lieu moi >> run_log.txt
) else (
    git commit -m "water level sample (local)" >> run_log.txt 2>&1
    git pull --rebase --autostash origin main >> run_log.txt 2>&1
    git push >> run_log.txt 2>&1
)
