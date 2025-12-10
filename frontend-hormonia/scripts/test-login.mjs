/**
 * Test Login Script
 * Tests Firebase authentication and backend session creation
 */

import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';

// Firebase config from .env
const firebaseConfig = {
  apiKey: "AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI",
  authDomain: "sistema-oncologico-auth.firebaseapp.com",
  projectId: "sistema-oncologico-auth",
  storageBucket: "sistema-oncologico-auth.appspot.com",
  messagingSenderId: "608742835827",
  appId: "1:608742835827:web:fa12840b0bd4949b7c8c06"
};

// Backend URL
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Test credentials
const EMAIL = 'admin@neoplasiaslitoral.com';
const PASSWORD = 'Admin@123456!';

async function testLogin() {
  console.log('🚀 Starting login test...\n');
  console.log('📧 Email:', EMAIL);
  console.log('🔑 Password:', '*'.repeat(PASSWORD.length));
  console.log('🌐 Backend:', BACKEND_URL);
  console.log('');

  try {
    // Step 1: Initialize Firebase
    console.log('📱 Step 1: Initializing Firebase...');
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    console.log('✅ Firebase initialized\n');

    // Step 2: Sign in with Firebase
    console.log('🔐 Step 2: Signing in with Firebase...');
    const userCredential = await signInWithEmailAndPassword(auth, EMAIL, PASSWORD);
    const user = userCredential.user;
    console.log('✅ Firebase login successful!');
    console.log('   User UID:', user.uid);
    console.log('   Email:', user.email);
    console.log('   Email Verified:', user.emailVerified);
    console.log('');

    // Step 3: Get ID Token
    console.log('🎫 Step 3: Getting Firebase ID token...');
    const idToken = await user.getIdToken();
    console.log('✅ ID Token obtained (first 50 chars):', idToken.substring(0, 50) + '...');
    console.log('   Token length:', idToken.length);
    console.log('');

    // Step 4: Create backend session
    console.log('🔗 Step 4: Creating backend session...');
    console.log('   POST', `${BACKEND_URL}/api/v2/auth/firebase/verify`);
    
    const response = await fetch(`${BACKEND_URL}/api/v2/auth/firebase/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        id_token: idToken
      })
    });

    console.log('   Response Status:', response.status, response.statusText);
    
    const responseData = await response.json();
    
    if (response.ok) {
      console.log('✅ Backend session created!');
      console.log('   Response:', JSON.stringify(responseData, null, 2));
    } else {
      console.log('❌ Backend session creation failed');
      console.log('   Error:', JSON.stringify(responseData, null, 2));
    }

    // Step 5: Verify session
    if (responseData.session_id) {
      console.log('\n🔍 Step 5: Verifying session...');
      console.log('   GET', `${BACKEND_URL}/api/v2/auth/verify-session`);
      
      const verifyResponse = await fetch(`${BACKEND_URL}/api/v2/auth/verify-session`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Cookie': `session_id=${responseData.session_id}`
        }
      });

      const verifyData = await verifyResponse.json();
      console.log('   Status:', verifyResponse.status);
      console.log('   Response:', JSON.stringify(verifyData, null, 2));
    }

    console.log('\n✅ Login test completed successfully!');
    
  } catch (error) {
    console.error('\n❌ Login test failed:', error.message);
    if (error.code) {
      console.error('   Error code:', error.code);
    }
    process.exit(1);
  }
}

testLogin();
