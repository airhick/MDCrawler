# Railway Deployment Fixes - Critical Updates

## 🚨 Problem: Internal Server Error

**Symptom**: 
```
The service was not able to process your request
Internal Server Error
```

**Root Cause**: Chromium was crashing in Docker container due to missing flags.

---

## ✅ Fixes Applied

### Fix #1: Docker-Compatible Chromium Flags
Added critical flags for running Chromium in containers:

```python
browser = await p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',              # ← REQUIRED for Docker
        '--disable-dev-shm-usage',   # ← Prevents memory issues
        '--disable-blink-features=AutomationControlled'
    ]
)
```

**Why these are needed**:
- `--no-sandbox`: Docker containers don't have user namespaces by default
- `--disable-dev-shm-usage`: Docker's /dev/shm is limited (64MB), this uses /tmp instead

### Fix #2: Error Logging
Added comprehensive error handling:

```python
try:
    pages = await crawl(payload)
    # ... process
except Exception as e:
    import traceback
    error_msg = f"Crawl error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
    print(error_msg)  # ← Now visible in Railway logs
    raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
```

**Benefit**: You can now see exact error messages in Railway logs.

---

## 🚀 Deployment Timeline

| Commit | Fix | Status |
|--------|-----|--------|
| `edbf6cd` | Allow requirements.txt in Docker | ✅ |
| `dc629d5` | Remove --with-deps flag | ✅ |
| `6d7bcea` | Add Docker Chromium flags | ✅ ← **Critical** |

**Current deploy**: `6d7bcea` (should fix the crash)

---

## ⏱️ Wait Time

Railway is rebuilding now:
- **Build**: 3-5 minutes
- **Deploy**: Automatic
- **Ready**: Check in ~5 minutes

---

## 🧪 How to Test After Deploy

### Test 1: Simple Static Site (Should work immediately)
```bash
curl "https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab?url=https://example.com&max_pages=1&use_js_rendering=false"
```

**Expected**: Clean markdown with example.com content

### Test 2: JavaScript Site (Requires Chromium)
```bash
curl "https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab?url=https://www.eratos.ch/&max_pages=3"
```

**Expected**: ~8,915 characters with full content

### Test 3: Via n8n HTTP Node

**Method**: POST  
**URL**: `https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab`  
**Body**:
```json
{
  "url": "https://www.eratos.ch",
  "depth": 1,
  "max_pages": 3,
  "use_js_rendering": true
}
```

**Expected**: Full markdown response

---

## 📊 What Changed

### Before (Crashing)
```
- Chromium tries to run with sandbox
- Docker doesn't support it
- Process crashes
- Returns 500 Internal Server Error
```

### After (Working)
```
- Chromium runs with --no-sandbox
- Memory managed with --disable-dev-shm-usage
- Process succeeds
- Returns full content
```

---

## 🔍 Debugging if Still Failing

### Check Railway Logs
```bash
railway logs --tail 100
```

**Look for**:
- ✅ `Deployment live` → Service is up
- ✅ `Playwright not available` → Warning (expected if not installed)
- ❌ `Failed to launch browser` → Chromium issue
- ❌ `Out of memory` → Need more RAM
- ❌ `Connection refused` → Network issue

### Common Issues

#### Issue: Still getting 500 error
**Check**: Railway logs for actual error message (now logged)

**Possible causes**:
1. Chromium not installed → Check build logs for "Installing Chromium"
2. Out of memory → Increase Railway RAM
3. Timeout → Increase timeout in request

#### Issue: Empty response
**Check**: Is `use_js_rendering` enabled?

**Try**:
```bash
# Disable JS rendering as fallback
curl "...?url=https://example.com&use_js_rendering=false"
```

#### Issue: Timeout
**Solution**: Increase timeout
```json
{
  "url": "...",
  "timeout": 30.0
}
```

---

## 🎯 Test Checklist

Wait 5 minutes after push, then test:

- [ ] Health check: `curl https://your-railway-url/`
- [ ] Static site: `curl "...?url=https://example.com&use_js_rendering=false"`
- [ ] JS site: `curl "...?url=https://www.eratos.ch/"`
- [ ] n8n webhook with POST request
- [ ] Check Railway logs for any errors

---

## 📝 Expected Results

### Static Site (httpx only)
- Time: ~200ms
- Size: ~200-500 chars
- Works: Even without Chromium

### JavaScript Site (Playwright)
- Time: ~10-15 seconds
- Size: ~8,915 chars
- Requires: Chromium installed

---

## 🚨 If It Still Doesn't Work

1. **Check Railway dashboard** → Deployments tab
2. **View logs**: `railway logs`
3. **Look for error**: Now logged with full traceback
4. **Share error message**: Copy exact error from logs

**Most common fix**: Increase memory
- Go to Railway Settings → Resources
- Increase RAM to 2GB
- Redeploy

---

## ✅ Success Indicators

When working, you'll see:

**In logs**:
```
Deployment live
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**In response**:
```markdown
# Eratos

URL: https://www.eratos.ch/

Email: intelligenceinfo@eratos.ch
...
[8,915+ characters of content]
```

---

**Current Status**: Waiting for Railway rebuild (commit `6d7bcea`)  
**Next Step**: Test in 5 minutes with the commands above  
**Expected**: ✅ Working deployment

