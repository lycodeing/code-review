<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-circle c1"></div>
      <div class="bg-circle c2"></div>
      <div class="bg-circle c3"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <el-icon :size="36" color="#409EFF"><Monitor /></el-icon>
        <h1>Code Review Admin</h1>
        <p>AI 驱动的代码审查管理平台</p>
      </div>

      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="rules"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item>
          <div class="login-options">
            <el-checkbox v-model="rememberMe">记住密码</el-checkbox>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span>默认账号: admin / admin123</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const rememberMe = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

/** 登录 */
async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login(loginForm)

    // 记住密码
    if (rememberMe.value) {
      localStorage.setItem('remembered_user', loginForm.username)
    } else {
      localStorage.removeItem('remembered_user')
    }

    ElMessage.success('登录成功')
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

// 恢复记住的用户名
onMounted(() => {
  const saved = localStorage.getItem('remembered_user')
  if (saved) {
    loginForm.username = saved
    rememberMe.value = true
  }
})
</script>

<style lang="scss" scoped>
.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f4fd 0%, #f0f5ff 50%, #e8f8f0 100%);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
}

.c1 {
  width: 400px;
  height: 400px;
  background: #409EFF;
  top: -100px;
  right: -80px;
}

.c2 {
  width: 300px;
  height: 300px;
  background: #67C23A;
  bottom: -60px;
  left: -60px;
}

.c3 {
  width: 200px;
  height: 200px;
  background: #E6A23C;
  top: 50%;
  left: 15%;
}

.login-card {
  width: 420px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  padding: 48px 40px 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 36px;

  h1 {
    font-size: 24px;
    color: #303133;
    margin: 12px 0 8px;
    font-weight: 700;
  }

  p {
    font-size: 14px;
    color: #909399;
  }
}

.login-options {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 8px;
  background: linear-gradient(135deg, #409EFF, #337ecc);
  border: none;

  &:hover {
    background: linear-gradient(135deg, #66b1ff, #409EFF);
  }
}

.login-footer {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
